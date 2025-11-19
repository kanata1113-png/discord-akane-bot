import discord
from discord.ext import commands, tasks
import openai
import httpx
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

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('akane_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# OpenAI設定
class OpenAIConfig:
    GPT_MODEL = "gpt-5.1"            # ← 新モデル名に更新
    # 必要あれば他の設定もここに追加

client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# タイムゾーン設定（日本時間）
JST = pytz.timezone('Asia/Tokyo')

class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    DATABASE_NAME = 'akane_data.db'
    REGULATION_ANALYSIS_MAX_TOKENS = 1200
    NORMAL_CHAT_MAX_TOKENS = 600

    GPT_MODEL = OpenAIConfig.GPT_MODEL

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

# 以下、データベース・分析クラス定義（変更不要部分略）

class DatabaseManager:
    """データベース管理クラス"""
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_log(user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_history(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_regulation_user ON regulation_analysis(user_id)')
        conn.commit()
        conn.close()
        logger.info("データベース初期化完了")

    def get_user_usage_today(self, user_id: str, username: str = None) -> int:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        today = datetime.now(JST).strftime('%Y-%m-%d')
        cursor.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
        result = cursor.fetchone()
        if username and result:
            cursor.execute('UPDATE usage_log SET username = ? WHERE user_id = ? AND date = ?', (username, user_id, today))
            conn.commit()
        conn.close()
        return result[0] if result else 0

    def increment_user_usage(self, user_id: str, username: str = None) -> int:
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
            cursor.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
            new_count = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return new_count

    def save_conversation(self, user_id: str, message: str, response: str,
                          is_regulation: bool = False, response_time_ms: int = None):
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
              scores.get('legal', 0), scores.get('purpose', 0),
              scores.get('proportion', 0), judgment, analysis, now.isoformat()))
        conn.commit()
        conn.close()

class ExpressionRegulationAnalyzer:
    """表現規制分析クラス"""
    def __init__(self):
        self.config = BotConfig()

    def detect_regulation_question(self, message: str) -> bool:
        has_regulation = any(keyword in message for keyword in self.config.REGULATION_KEYWORDS)
        has_question = any(keyword in message for keyword in self.config.QUESTION_KEYWORDS)
        question_patterns = [r'.*？$', r'.*\?$', r'^.*ですか.*', r'^.*やろか.*', r'^.*かな.*']
        has_question_pattern = any(re.search(pattern, message) for pattern in question_patterns)
        return has_regulation and (has_question or has_question_pattern)

    def extract_regulation_target(self, message: str) -> str:
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

        self.stats = {
            'total_messages': 0,
            'regulation_analyses': 0,
            'unique_users': set(),
            'errors': 0
        }

    async def setup_hook(self):
        self.cleanup_old_data.start()
        self.update_stats.start()

    @tasks.loop(hours=24)
    async def cleanup_old_data(self):
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()
            cutoff_date = (datetime.now(JST) - timedelta(days=30)).isoformat()
            cursor.execute('DELETE FROM conversation_history WHERE timestamp < ?', (cutoff_date,))
            cutoff_date2 = (datetime.now(JST) - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute('DELETE FROM usage_log WHERE date < ?', (cutoff_date2,))
            conn.commit()
            conn.close()
            logger.info("古いデータのクリーンアップ完了")
        except Exception as e:
            logger.error(f"データクリーンアップエラー: {e}")

    @tasks.loop(hours=1)
    async def update_stats(self):
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()
            today = datetime.now(JST).strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM usage_log WHERE date = ?', (today,))
            active_users_today = cursor.fetchone()[0]
            conn.close()
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=f"表現の自由について♪ (今日: {active_users_today}人)"
            )
            await self.change_presence(activity=activity)
        except Exception as e:
            logger.error(f"統計更新エラー: {e}")

    async def on_ready(self):
        logger.info(f'茜ちゃんが起動したで〜！ {self.user}')
        logger.info(f'参加サーバー数: {len(self.guilds)}')
        logger.info(f'GPTモデル使用モード: {self.config.GPT_MODEL}')

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
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat_message(message)
        await self.process_commands(message)

    async def handle_chat_message(self, message):
        start_time = datetime.now()
        user_id = str(message.author.id)
        username = message.author.display_name

        self.stats['total_messages'] += 1
        self.stats['unique_users'].add(user_id)

        usage_today = self.db.get_user_usage_today(user_id, username)
        if usage_today >= self.config.DAILY_MESSAGE_LIMIT:
            await self.send_limit_reached_message(message, usage_today)
            return

        new_usage = self.db.increment_user_usage(user_id, username)

        try:
            async with message.channel.typing():
                user_message = self.preprocess_message(message.content)
                is_regulation = self.analyzer.detect_regulation_question(user_message)

                if is_regulation:
                    response = await self.handle_regulation_analysis(user_message, user_id, username)
                    self.stats['regulation_analyses'] += 1
                else:
                    response = await self.handle_normal_chat(user_message, user_id, username)

                await self.send_response(message, response, is_regulation)
                response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self.db.save_conversation(user_id, user_message, response, is_regulation, response_time_ms)

                if new_usage % 20 == 0 or new_usage >= 90:
                    await self.send_usage_notification(message, new_usage)

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"メッセージ処理エラー: {e}")
            await self.send_error_message(message)

    def preprocess_message(self, content: str) -> str:
        content = re.sub(r'<@!?\d+>', '', content)
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    async def handle_regulation_analysis(self, message: str, user_id: str, username: str) -> str:
        target = self.analyzer.extract_regulation_target(message)
        prompt = self.analyzer.create_analysis_prompt(message, target)
        try:
            response = await self.call_gpt_with_retry(
                system_prompt=prompt,
                user_message=message,
                max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS,
                reasoning_effort="minimal",      # 分析用途なので少し大きめに
                temperature=0.6
            )
            scores = self.analyzer.extract_scores_from_response(response)
            judgment = self.analyzer.extract_judgment_from_response(response)
            self.db.save_regulation_analysis(user_id, target, message, scores, judgment, response)
            return response
        except Exception as e:
            logger.error(f"表現規制分析エラー: {e}")
            return "ごめんな〜、分析機能でちょっとトラブルがあったみたいや😅 また聞いてくれたら嬉しいで♪"

    async def call_gpt_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 500,
        reasoning_effort: str = "none",
        temperature: float = 0.8,
        max_retries: int = 3
    ) -> str:
        """GPT-5.1 対応版：max_completion_tokens を使用"""
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message}
                    ],
                    max_completion_tokens = max_tokens,         # ← 旧 max_tokens を変更
                    reasoning_effort     = reasoning_effort,    # ← 新パラメータ
                    # ※ temperature 等のパラメータはモデル仕様によっては無効になります
                )
                return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"GPT呼び出し失敗 (試行 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        raise RuntimeError("GPT 呼び出しが全試行とも失敗しました")

    async def send_response(self, message, response: str, is_regulation: bool = False):
        if is_regulation:
            embed = discord.Embed(
                title="📋 表現規制審査結果",
                color=0xffd700,
                timestamp=datetime.now(JST)
            )
            if len(response) <= 1024:
                embed.add_field(name="茜の詳細分析", value=response, inline=False)
            else:
                parts = self.split_text_smartly(response, 1024)
                for i, part in enumerate(parts[:3]):
                    name = "茜の詳細分析" if i == 0 else f"続き ({i+1})"
                    embed.add_field(name=name, value=part, inline=False)
            embed.set_footer(text="表現の自由は民主主義の基盤やからね！")
            await message.reply(embed=embed)
            if len(response) > 3072:
                remaining = response[3072:]
                await message.channel.send(f"**続き:**\n{remaining}")
        else:
            if len(response) <= self.config.MAX_RESPONSE_LENGTH:
                await message.reply(response)
            else:
                parts = self.split_text_smartly(response, self.config.MAX_RESPONSE_LENGTH)
                for part in parts:
                    await message.channel.send(part)

    def split_text_smartly(self, text: str, max_length: int) -> List[str]:
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
        remaining = self.config.DAILY_MESSAGE_LIMIT - usage_count
        if remaining <= 10:
            color = 0xff6b6b
            icon = "⚠️"
            msg = f"あと{remaining}回で今日の制限やで〜"
        elif remaining <= 30:
            color = 0xffa500
            icon = "📊"
            msg = f"今日はあと{remaining}回お話しできるで〜"
        else:
            color = 0x87ceeb
            icon = "📈"
            msg = f"今日はあと{remaining}回お話しできるで〜"
        embed = discord.Embed(
            title=f"{icon} 使用状況",
            description=msg,
            color=color
        )
        await message.channel.send(embed=embed)

    async def send_error_message(self, message):
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
        now = datetime.now(JST)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        remaining = tomorrow - now
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        return f"{hours}時間{minutes}分"

    @commands.command(name='usage')
    async def check_usage(self, ctx):
        user_id = str(ctx.author.id)
        username = ctx.author.display_name
        usage_today = self.db.get_user_usage_today(user_id, username)
        remaining = self.config.DAILY_MESSAGE_LIMIT - usage_today
        embed = discord.Embed(
            title="📊 茜ちゃんとの会話記録",
            color=0x87ceeb,
            timestamp=datetime.now(JST)
        )
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
        uptime = datetime.now(JST) - self.start_time
        uptime_str = str(uptime).split('.')[0]
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
    required_env = ['DISCORD_TOKEN', 'OPENAI_API_KEY']
    missing_env = [env for env in required_env if not os.getenv(env)]
    if missing_env:
        logger.error(f"必要な環境変数が設定されていません: {missing_env}")
        exit(1)

    bot = AkaneBot()
    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except discord.LoginFailure:
        logger.error("無効なDiscordトークンです。DISCORD_TOKENを確認してください。")
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
