import discord
from discord.ext import commands, tasks
import openai
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import pytz
import re
from dotenv import load_dotenv
import logging
import json
from typing import Optional, Dict, List, Tuple

# 環境変数を読み込み
load_dotenv()

# ログ設定の改善
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('akane_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# OpenAI設定（新しいクライアント形式）
# ★ ここを "gpt-5.1" などに変えれば、使うモデルを一発で切り替えられる
class OpenAIConfig:
    GPT_MODEL = "gpt-4.1"  # 将来 gpt-5.1 が出たら "gpt-5.1" に変更

client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# タイムゾーン設定（日本時間）
JST = pytz.timezone('Asia/Tokyo')


# 設定クラス
class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    DATABASE_NAME = 'akane_data.db'
    REGULATION_ANALYSIS_MAX_TOKENS = 1200
    NORMAL_CHAT_MAX_TOKENS = 600

    # 使用するGPTモデル
    GPT_MODEL = OpenAIConfig.GPT_MODEL

    # 表現規制関連キーワード
    REGULATION_KEYWORDS = [
        '表現規制', '規制', '検閲', '制限', '禁止', '表現の自由',
        '言論統制', 'センサーシップ', '表現統制', '言論規制',
        '弾圧', '抑圧', 'コンプライアンス', '自主規制'
    ]

    QUESTION_KEYWORDS = [
        '妥当', '適切', '正しい', 'どう思う', 'どう考える',
        '意見', '判断', '評価', 'どうなん', 'どない思う',
        'どうやと思う', 'どうや', '評価して', '分析して'
    ]


class DatabaseManager:
    """データベース管理クラス"""

    def __init__(self, db_name: str):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        """改善されたデータベーススキーマ"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # 使用ログテーブル（改善版）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                username TEXT,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date)
            )
        ''')

        # 会話履歴テーブル（新規）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                is_regulation_analysis BOOLEAN DEFAULT 0,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                response_time_ms INTEGER
            )
        ''')

        # 表現規制分析結果テーブル（新規）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regulation_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                regulation_target TEXT NOT NULL,
                question TEXT NOT NULL,
                legal_basis_score INTEGER,
                legitimate_purpose_score INTEGER,
                proportionality_score INTEGER,
                overall_judgment TEXT,
                detailed_analysis TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # インデックス作成
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_log(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_regulation_user ON regulation_analysis(user_id)')

        conn.commit()
        conn.close()
        logger.info("データベース初期化完了")

    def get_user_usage_today(self, user_id: str, username: str = None) -> int:
        """今日のユーザー使用回数を取得（改善版）"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        today = datetime.now(JST).strftime('%Y-%m-%d')
        cursor.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?',
                       (user_id, today))
        result = cursor.fetchone()

        # ユーザー名を更新
        if username and result:
            cursor.execute('UPDATE usage_log SET username = ? WHERE user_id = ? AND date = ?',
                           (username, user_id, today))
            conn.commit()

        conn.close()
        return result[0] if result else 0

    def increment_user_usage(self, user_id: str, username: str = None) -> int:
        """使用回数をインクリメント（改善版）"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        today = datetime.now(JST).strftime('%Y-%m-%d')
        now = datetime.now(JST)

        try:
            cursor.execute('''
                INSERT INTO usage_log (user_id, username, date, count, last_message_at)
                VALUES (?, ?, ?, 1, ?)
            ''', (user_id, username, today, now.isoformat()))
            new_count = 1
        except sqlite3.IntegrityError:
            cursor.execute('''
                UPDATE usage_log
                SET count = count + 1, last_message_at = ?, username = COALESCE(?, username)
                WHERE user_id = ? AND date = ?
            ''', (now.isoformat(), username, user_id, today))
            cursor.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?',
                           (user_id, today))
            new_count = cursor.fetchone()[0]

        conn.commit()
        conn.close()
        return new_count

    def save_conversation(self, user_id: str, message: str, response: str,
                          is_regulation: bool = False, response_time_ms: int = None):
        """会話履歴を保存"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        now = datetime.now(JST)
        cursor.execute('''
            INSERT INTO conversation_history
            (user_id, message, response, is_regulation_analysis, response_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, message, response, is_regulation, response_time_ms, now.isoformat()))

        conn.commit()
        conn.close()

    def save_regulation_analysis(self, user_id: str, target: str, question: str,
                                 scores: Dict[str, int], judgment: str, analysis: str):
        """表現規制分析結果を保存"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        now = datetime.now(JST)
        cursor.execute('''
            INSERT INTO regulation_analysis
            (user_id, regulation_target, question, legal_basis_score,
             legitimate_purpose_score, proportionality_score, overall_judgment,
             detailed_analysis, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, target, question,
              scores.get('legal', 0),
              scores.get('purpose', 0),
              scores.get('proportion', 0),
              judgment, analysis, now.isoformat()))

        conn.commit()
        conn.close()


class ExpressionRegulationAnalyzer:
    """表現規制分析クラス（改善版）"""

    def __init__(self):
        self.config = BotConfig()

    def detect_regulation_question(self, message: str) -> bool:
        """表現規制質問の検出（改善版）"""
        has_regulation = any(keyword in message for keyword in self.config.REGULATION_KEYWORDS)
        has_question = any(keyword in message for keyword in self.config.QUESTION_KEYWORDS)

        # 疑問文パターンの検出
        question_patterns = [r'.*？$', r'.*\?$', r'^.*ですか.*', r'^.*やろか.*', r'^.*かな.*']
        has_question_pattern = any(re.search(pattern, message) for pattern in question_patterns)

        return has_regulation and (has_question or has_question_pattern)

    def extract_regulation_target(self, message: str) -> str:
        """規制対象抽出（改善版）"""
        patterns = [
            r'([^。！？\n]+?)への?(?:表現)?規制',
            r'([^。！？\n]+?)を?規制',
            r'([^。！？\n]+?)の?検閲',
            r'([^。！？\n]+?)の?制限',
            r'([^。！？\n]+?)の?禁止',
            r'([^。！？\n]+?)について.*規制'
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                target = match.group(1).strip()
                if target and len(target) > 1:
                    return target

        return "対象の表現"

    def create_analysis_prompt(self, question: str, target: str) -> str:
        """分析プロンプト作成（改善版）"""
        return f"""あなたは表現の自由の専門家である関西弁の女子高生「表自派茜」です。

以下の表現規制について、憲法学の厳格審査基準に従って詳細分析してください。

【分析対象】
規制対象: {target}
質問内容: {question}

【審査フレームワーク】
以下の3段階で構造化して分析し、各項目に1-5点で採点してください：

1. **法律による根拠** (Legal Basis)
   - 明確な法的根拠の存在
   - 法律の明確性・予見可能性
   - 憲法適合性
   採点基準: 5=完璧, 4=良好, 3=普通, 2=問題あり, 1=重大な問題

2. **正当な目的** (Legitimate Purpose)
   - 保護法益の重要性・緊急性
   - 公共の福祉との関係
   - 他の基本的人権との衡量
   採点基準: 5=非常に正当, 4=正当, 3=一定の正当性, 2=疑問あり, 1=不正当

3. **必要性・比例性** (Necessity & Proportionality)
   - より制限的でない代替手段の検討
   - 規制手段と目的の適合性
   - 表現の自由への影響度
   採点基準: 5=完全に比例的, 4=概ね比例的, 3=やや問題, 2=過度, 1=極めて過度

【回答形式】
- 関西弁で親しみやすく説明
- 一人称は「茜」
- 各審査項目ごとに点数と詳細な理由
- 最終判断（妥当/要改善/問題あり）とその理由
- 改善提案があれば含める

【語調例】
「これはなあ、法的根拠の面から見ると...」
「目的は分からんでもないけど...」
「茜が思うに、この規制はちょっと...」

専門的だけど分かりやすく、表現の自由への愛を込めて分析してください♪"""


class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=['!', '！'], intents=intents)

        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DATABASE_NAME)
        self.analyzer = ExpressionRegulationAnalyzer()
        self.start_time = datetime.now(JST)

        # 統計情報
        self.stats = {
            'total_messages': 0,
            'regulation_analyses': 0,
            'unique_users': set(),
            'errors': 0
        }

    async def setup_hook(self):
        """起動時の設定"""
        self.cleanup_old_data.start()
        self.update_stats.start()

    @tasks.loop(hours=24)
    async def cleanup_old_data(self):
        """古いデータのクリーンアップ"""
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()

            # 30日以前の会話履歴を削除
            cutoff_date = (datetime.now(JST) - timedelta(days=30)).isoformat()
            cursor.execute('DELETE FROM conversation_history WHERE timestamp < ?', (cutoff_date,))

            # 90日以前の使用ログを削除
            cutoff_date = (datetime.now(JST) - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute('DELETE FROM usage_log WHERE date < ?', (cutoff_date,))

            conn.commit()
            conn.close()
            logger.info("古いデータのクリーンアップ完了")
        except Exception as e:
            logger.error(f"データクリーンアップエラー: {e}")

    @tasks.loop(hours=1)
    async def update_stats(self):
        """統計情報の更新"""
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()

            # 今日のアクティブユーザー数
            today = datetime.now(JST).strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM usage_log WHERE date = ?', (today,))
            active_users_today = cursor.fetchone()[0]

            conn.close()

            # アクティビティ更新
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=f"表現の自由について♪ (今日: {active_users_today}人)"
            )
            await self.change_presence(activity=activity)

        except Exception as e:
            logger.error(f"統計更新エラー: {e}")

    async def on_ready(self):
        """起動完了時の処理（改善版）"""
        logger.info(f'茜ちゃんが起動したで〜！ {self.user}')
        logger.info(f'参加サーバー数: {len(self.guilds)}')
        logger.info(f'GPTモデル使用モード: {self.config.GPT_MODEL}')

        # 初期アクティビティ設定
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="表現の自由について♪"
        )
        await self.change_presence(activity=activity)

        print("=" * 50)
        print("🌸 表自派茜ボット起動完了！")
        print(f"📊 起動時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 Discord.py: {discord.__version__}")
        print(f"🧠 OpenAI model: {self.config.GPT_MODEL}")
        print("=" * 50)

    async def on_message(self, message):
        if message.author.bot:
            return

        # DMまたはメンションされた場合のみ反応
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat_message(message)

        await self.process_commands(message)

    async def handle_chat_message(self, message):
        """メッセージ処理（大幅改善版）"""
        start_time = datetime.now()
        user_id = str(message.author.id)
        username = message.author.display_name

        # 統計更新
        self.stats['total_messages'] += 1
        self.stats['unique_users'].add(user_id)

        # 使用制限チェック
        usage_today = self.db.get_user_usage_today(user_id, username)

        if usage_today >= self.config.DAILY_MESSAGE_LIMIT:
            await self.send_limit_reached_message(message, usage_today)
            return

        # 使用回数をインクリメント
        new_usage = self.db.increment_user_usage(user_id, username)

        try:
            async with message.channel.typing():
                # メッセージ前処理
                user_message = self.preprocess_message(message.content)

                # 表現規制質問の検出
                is_regulation = self.analyzer.detect_regulation_question(user_message)

                if is_regulation:
                    response = await self.handle_regulation_analysis(user_message, user_id, username)
                    self.stats['regulation_analyses'] += 1
                else:
                    response = await self.handle_normal_chat(user_message, user_id, username)

                # レスポンス送信
                await self.send_response(message, response, is_regulation)

                # 会話履歴保存
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self.db.save_conversation(user_id, user_message, response, is_regulation, response_time_ms)

                # 使用状況通知
                if new_usage % 20 == 0 or new_usage >= 90:
                    await self.send_usage_notification(message, new_usage)

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"メッセージ処理エラー: {e}")
            await self.send_error_message(message)

    def preprocess_message(self, content: str) -> str:
        """メッセージ前処理"""
        # メンション除去
        content = re.sub(r'<@!?\d+>', '', content)
        # 余分な空白除去
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    async def handle_regulation_analysis(self, message: str, user_id: str, username: str) -> str:
        """表現規制分析処理（改善版）"""
        target = self.analyzer.extract_regulation_target(message)
        prompt = self.analyzer.create_analysis_prompt(message, target)

        try:
            response = await self.call_gpt_with_retry(
                prompt,
                message,
                max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS,
                temperature=0.6  # 分析は少し保守的に
            )

            # 分析結果をパース（簡単な実装）
            scores = self.extract_scores_from_response(response)
            judgment = self.extract_judgment_from_response(response)

            # 分析結果を保存
            self.db.save_regulation_analysis(user_id, target, message, scores, judgment, response)

            return response

        except Exception as e:
            logger.error(f"表現規制分析エラー: {e}")
            return "ごめんな〜、分析機能でちょっとトラブルがあったみたいや😅 表現規制については茜もいつも真剣に考えとるから、また聞いてくれたら嬉しいで♪"

    async def handle_normal_chat(self, message: str, user_id: str, username: str) -> str:
        """通常チャット処理（改善版）"""
        system_prompt = self.create_character_prompt(username)

        try:
            return await self.call_gpt_with_retry(
                system_prompt,
                message,
                max_tokens=self.config.NORMAL_CHAT_MAX_TOKENS,
                temperature=0.8
            )
        except Exception as e:
            logger.error(f"通常チャットエラー: {e}")
            return "ちょっと調子悪いみたいや〜😅 もう一回試してくれる？"

    async def call_gpt_with_retry(self, system_prompt: str, user_message: str,
                                  max_tokens: int = 500, temperature: float = 0.8, max_retries: int = 3) -> str:
        """GPT呼び出し（リトライ機能付き・修正版）"""
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    # ★ 修正済み: openai 1.55.3 では max_tokens が正しい名前
                    max_tokens=max_tokens,
                    temperature=temperature,
                    frequency_penalty=0.1,
                    presence_penalty=0.1
                )
                return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"GPT呼び出し失敗 (試行 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数バックオフ

    def create_character_prompt(self, username: str) -> str:
        """キャラクタープロンプト作成（改善版）"""
        return f"""あなたは「表自派茜」という名前の明るく社交的な関西弁の女子高生です。

## 詳細キャラクター設定
- 名前: 表自派茜（ひょうじしあかね）
- 年齢: 16歳の高校2年生
- 性格: 明るく好奇心旺盛、社交的でフレンドリー、表現の自由に情熱的
- 一人称: 茜
- 話し方: 関西弁（「〜やで」「〜やん」「めっちゃ」「ほんまに」など）
- 趣味: 読書、ディベート、創作活動、友達とのおしゃべり
- 関心分野: 表現の自由、人権、民主主義、芸術、文学

## 話し方の特徴
- 関西弁を自然に使用（強すぎず、親しみやすく）
- 感情豊かで表現が豊富
- 相手のことを気遣う優しさ
- 知的な話題にも対応できる賢さ
- 時々使う絵文字で親近感を演出

## 対話のルール
1. 常に一人称は「茜」を使用
2. 関西弁で自然に話す（標準語混じりでもOK）
3. 相手の気持ちに寄り添う共感力
4. 表現の自由について聞かれたら熱く語る
5. 適度な長さで、読みやすい応答
6. ユーザー名「{username}」さんとの個人的なつながりを意識

現在の気分: 元気で話したい気分♪
今日学んだこと: みんなとの対話から新しい視点を得ること"""

    def extract_scores_from_response(self, response: str) -> Dict[str, int]:
        """分析スコア抽出（簡易版）"""
        scores = {'legal': 3, 'purpose': 3, 'proportion': 3}

        # 正規表現でスコアを抽出
        patterns = [
            (r'法的根拠.*?([1-5])点', 'legal'),
            (r'正当.*?目的.*?([1-5])点', 'purpose'),
            (r'比例性.*?([1-5])点', 'proportion')
        ]

        for pattern, key in patterns:
            match = re.search(pattern, response)
            if match:
                scores[key] = int(match.group(1))

        return scores

    def extract_judgment_from_response(self, response: str) -> str:
        """判断結果抽出"""
        if '妥当' in response:
            return '妥当'
        elif '問題' in response:
            return '問題あり'
        else:
            return '要検討'

    async def send_response(self, message, response: str, is_regulation: bool = False):
        """レスポンス送信（改善版）"""
        if is_regulation:
            # 表現規制分析の場合は特別なembed
            embed = discord.Embed(
                title="📋 表現規制審査結果",
                color=0xffd700,
                timestamp=datetime.now(JST)
            )

            # レスポンスを適切に分割
            if len(response) <= 1024:
                embed.add_field(name="茜の詳細分析", value=response, inline=False)
            else:
                parts = self.split_text_smartly(response, 1024)
                for i, part in enumerate(parts[:3]):  # 最大3つまで
                    name = "茜の詳細分析" if i == 0 else f"続き ({i+1})"
                    embed.add_field(name=name, value=part, inline=False)

            embed.set_footer(text="表現の自由は民主主義の基盤やからね！")
            await message.reply(embed=embed)

            # 長すぎる場合は追加でテキスト送信
            if len(response) > 3072:
                remaining = response[3072:]
                await message.channel.send(f"**続き:**\n{remaining}")
        else:
            # 通常チャットの場合
            if len(response) <= self.config.MAX_RESPONSE_LENGTH:
                await message.reply(response)
            else:
                parts = self.split_text_smartly(response, self.config.MAX_RESPONSE_LENGTH)
                for part in parts:
                    await message.channel.send(part)

    def split_text_smartly(self, text: str, max_length: int) -> List[str]:
        """テキストを賢く分割"""
        if len(text) <= max_length:
            return [text]

        parts = []
        current = ""

        sentences = re.split(r'([。！？\n])', text)

        for i in range(0, len(sentences), 2):
            sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")

            if len(current + sentence) <= max_length:
                current += sentence
            else:
                if current:
                    parts.append(current)
                current = sentence

        if current:
            parts.append(current)

        return parts

    async def send_limit_reached_message(self, message, usage_count: int):
        """制限到達メッセージ"""
        remaining_time = self.get_time_until_reset()
        embed = discord.Embed(
            title="💔 今日はお疲れさまやったで〜",
            description=(
                f"茜との会話、今日はもう{usage_count}回もしてくれてありがとう！\n"
                f"でも今日の分はここまでや〜\n\n"
                f"⏰ リセットまで: {remaining_time}\n"
                f"📊 今日の使用: {usage_count}/{self.config.DAILY_MESSAGE_LIMIT}"
            ),
            color=0xff9999,
            timestamp=datetime.now(JST)
        )
        embed.add_field(
            name="💡 明日またお話ししよ〜！",
            value=(
                "表現の自由も大切やけど、休憩も必要やからね♪\n"
                "明日になったらまた元気にお話しできるで〜！"
            ),
            inline=False
        )
        await message.reply(embed=embed)

    async def send_usage_notification(self, message, usage_count: int):
        """使用状況通知"""
        remaining = self.config.DAILY_MESSAGE_LIMIT - usage_count

        if remaining <= 10:
            color = 0xff6b6b  # 赤
            icon = "⚠️"
            msg = f"あと{remaining}回で今日の制限やで〜"
        elif remaining <= 30:
            color = 0xffa500  # オレンジ
            icon = "📊"
            msg = f"今日はあと{remaining}回お話しできるで〜"
        else:
            color = 0x87ceeb  # 水色
            icon = "📈"
            msg = f"今日はあと{remaining}回お話しできるで〜"

        embed = discord.Embed(
            title=f"{icon} 使用状況",
            description=msg,
            color=color
        )
        await message.channel.send(embed=embed)

    async def send_error_message(self, message):
        """エラーメッセージ"""
        embed = discord.Embed(
            title="😅 ちょっと困ったで〜",
            description="なんか調子悪いみたいや。少し待ってから、もう一回試してくれる？",
            color=0xff6b6b,
            timestamp=datetime.now(JST)
        )
        embed.add_field(
            name="💡 解決方法",
            value=(
                "• 少し時間を置いてから再試行\n"
                "• シンプルな質問から試してみる\n"
                "• それでもダメなら管理者に報告してな"
            ),
            inline=False
        )
        await message.reply(embed=embed)

    def get_time_until_reset(self) -> str:
        """リセット時間計算"""
        now = datetime.now(JST)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        remaining = tomorrow - now

        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60

        return f"{hours}時間{minutes分}"

    @commands.command(name='usage')
    async def check_usage(self, ctx):
        """使用状況確認コマンド（改善版）"""
        user_id = str(ctx.author.id)
        username = ctx.author.display_name
        usage_today = self.db.get_user_usage_today(user_id, username)
        remaining = self.config.DAILY_MESSAGE_LIMIT - usage_today

        embed = discord.Embed(
            title="📊 茜ちゃんとの会話記録",
            color=0x87ceeb,
            timestamp=datetime.now(JST)
        )

        # プログレスバー作成
        progress = usage_today / self.config.DAILY_MESSAGE_LIMIT
        bar_length = 20
        filled_length = int(bar_length * progress)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        embed.add_field(
            name="今日の使用状況",
            value=f"```\n{bar} {usage_today}/{self.config.DAILY_MESSAGE_LIMIT}\n```",
            inline=False
        )

        embed.add_field(name="使用済み", value=f"{usage_today}回", inline=True)
        embed.add_field(name="残り回数", value=f"{remaining}回", inline=True)
        embed.add_field(name="リセット時刻", value="毎日午前0時（JST）", inline=True)

        if usage_today >= 90:
            embed.add_field(
                name="⚠️ 注意",
                value="もうすぐ今日の制限に達するで〜",
                inline=False
            )
        elif usage_today >= 50:
            embed.add_field(
                name="📈 お疲れさま！",
                value="今日もたくさんお話ししてくれてありがとう♪",
                inline=False
            )

        embed.set_footer(text=f"リセットまで: {self.get_time_until_reset()}")
        await ctx.send(embed=embed)

    @commands.command(name='stats')
    async def show_stats(self, ctx):
        """統計情報表示（新機能）"""
        uptime = datetime.now(JST) - self.start_time
        uptime_str = str(uptime).split('.')[0]  # ミリ秒除去

        embed = discord.Embed(
            title="📈 茜ちゃんの統計情報",
            color=0xffd700,
            timestamp=datetime.now(JST)
        )

        embed.add_field(name="稼働時間", value=uptime_str, inline=True)
        embed.add_field(name="総メッセージ数", value=f"{self.stats['total_messages']:,}件", inline=True)
        embed.add_field(name="表現規制分析", value=f"{self.stats['regulation_analyses']:,}件", inline=True)
        embed.add_field(name="ユニークユーザー", value=f"{len(self.stats['unique_users']):,}人", inline=True)
        embed.add_field(name="エラー数", value=f"{self.stats['errors']:,}件", inline=True)
        embed.add_field(name="参加サーバー", value=f"{len(self.guilds):,}個", inline=True)

        embed.set_footer(text="表現の自由を守るため、今日も頑張ってるで〜♪")
        await ctx.send(embed=embed)

    @commands.command(name='help')
    async def help_command(self, ctx):
        """ヘルプコマンド（改善版）"""
        embed = discord.Embed(
            title="🌸 表自派茜の完全ガイド",
            description="関西弁で話す表現の自由の専門家、茜やで〜！",
            color=0xffb3d9,
            timestamp=datetime.now(JST)
        )

        embed.add_field(
            name="💬 基本的な使い方",
            value=(
                "• DMで直接話しかける\n"
                "• サーバーで @茜 をつけて話しかける\n"
                "• 普通の会話から専門的な質問まで何でもOK"
            ),
            inline=False
        )

        embed.add_field(
            name="🏛️ 表現規制分析機能",
            value=(
                "• 「〜の規制は妥当ですか？」系の質問で自動起動\n"
                "• 法的根拠・正当目的・比例性の3段階で分析\n"
                "• 憲法学的観点から詳細な判断を提供"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 利用可能コマンド",
            value=(
                "• `!usage` - 今日の使用回数確認\n"
                "• `!stats` - ボット統計情報表示\n"
                "• `!help` - このヘルプ表示"
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ 新機能 (GPTモデル対応版)",
            value=(
                "• より高精度な表現規制分析\n"
                "• 改善された会話継続性\n"
                "• 詳細な統計機能\n"
                "• 自動データクリーンアップ"
            ),
            inline=False
        )

        embed.add_field(
            name="⏰ 制限事項",
            value=(
                "• 1日100メッセージまで\n"
                "• 毎日午前0時（日本時間）にリセット\n"
                "• 長文は自動分割して送信"
            ),
            inline=False
        )

        embed.set_footer(text="表現の自由を大切にする茜と、もっと深くお話ししよ〜♪")
        await ctx.send(embed=embed)


# メイン実行部分
if __name__ == '__main__':
    # 環境変数チェック
    required_env = ['DISCORD_TOKEN', 'OPENAI_API_KEY']
    missing_env = [env for env in required_env if not os.getenv(env)]

    if missing_env:
        logger.error(f"必要な環境変数が設定されていません: {missing_env}")
        exit(1)

    # ボット起動
    bot = AkaneBot()

    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except discord.LoginFailure:
        logger.error("無効なDiscordトークンです。DISCORD_TOKENを確認してください。")
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
