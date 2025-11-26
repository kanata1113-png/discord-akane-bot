import discord
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import httpx
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import pytz
import re
from dotenv import load_dotenv
import logging
from typing import Dict, List, Optional

# =========================
# 環境変数・ログ設定
# =========================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================
# OpenAI 設定 (GPT-5.1)
# =========================

class OpenAIConfig:
    # ★修正: 2025年11月リリースの最新モデルを指定
    # "gpt-5.1" は適応型推論(Adaptive Reasoning)を搭載したフラッグシップ
    GPT_MODEL = "gpt-5.1"

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
JST = pytz.timezone('Asia/Tokyo')

# =========================
# Bot 全体設定
# =========================

class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    
    # Railway Volume対応
    if os.path.exists("/data"):
        DATABASE_NAME = '/data/akane_data.db'
    else:
        DATABASE_NAME = 'akane_data.db'

    # GPT-5.1 はコンテキスト効率が良いが、念のためトークン数は確保
    REGULATION_ANALYSIS_MAX_TOKENS = 2000
    NORMAL_CHAT_MAX_TOKENS = 1000

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

# =========================
# DB 管理 (変更なし)
# =========================

class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        db_dir = os.path.dirname(self.db_name)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

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
        conn.commit()
        conn.close()

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
            cursor.execute('INSERT INTO usage_log (user_id, username, date, count, last_message_at) VALUES (?, ?, ?, 1, ?)', 
                           (user_id, username, today, now.isoformat()))
            new_count = 1
        except sqlite3.IntegrityError:
            cursor.execute('UPDATE usage_log SET count = count + 1, last_message_at = ?, username = COALESCE(?, username) WHERE user_id = ? AND date = ?', 
                           (now.isoformat(), username, user_id, today))
            cursor.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
            new_count = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return new_count

    def save_conversation(self, user_id: str, message: str, response: str, is_regulation: bool, response_time_ms: int):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        now = datetime.now(JST)
        cursor.execute('INSERT INTO conversation_history (user_id, message, response, is_regulation_analysis, response_time_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?)', 
                       (user_id, message, response, is_regulation, response_time_ms, now.isoformat()))
        conn.commit()
        conn.close()

    def save_regulation_analysis(self, user_id: str, target: str, question: str, scores: Dict[str, int], judgment: str, analysis: str):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        now = datetime.now(JST)
        cursor.execute('INSERT INTO regulation_analysis (user_id, regulation_target, question, legal_basis_score, legitimate_purpose_score, proportionality_score, overall_judgment, detailed_analysis, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                       (user_id, target, question, scores.get('legal',0), scores.get('purpose',0), scores.get('proportion',0), judgment, analysis, now.isoformat()))
        conn.commit()
        conn.close()

# =========================
# 表現規制分析
# =========================

class ExpressionRegulationAnalyzer:
    def __init__(self):
        self.config = BotConfig()

    def detect_regulation_question(self, message: str) -> bool:
        has_regulation = any(k in message for k in self.config.REGULATION_KEYWORDS)
        has_question = any(k in message for k in self.config.QUESTION_KEYWORDS)
        question_patterns = [r'.*？$', r'.*\?$', r'^.*ですか.*', r'^.*やろか.*', r'^.*かな.*']
        return has_regulation and (has_question or any(re.search(p, message) for p in question_patterns))

    def extract_regulation_target(self, message: str) -> str:
        patterns = [
            r'([^。！？\n]+?)への?(?:表現)?規制', r'([^。！？\n]+?)を?規制',
            r'([^。！？\n]+?)の?検閲', r'([^。！？\n]+?)の?制限',
            r'([^。！？\n]+?)の?禁止', r'([^。！？\n]+?)について.*規制'
        ]
        for pattern in patterns:
            m = re.search(pattern, message)
            if m:
                target = m.group(1).strip()
                if len(target) > 1: return target
        return "対象の表現"

    def create_analysis_prompt(self, question: str, target: str) -> str:
        # GPT-5.1は指示従順性が高いため、より構造化して指示
        return f"""あなたは「表自派茜」という、表現の自由を愛する関西弁の女子高生です。

以下のトピックについて、憲法学の厳格審査基準（Strict Scrutiny）のフレームワークを用いて分析を行ってください。

【トピック】
対象: {target}
問い: {question}

【思考プロセス】
1. 法律による根拠 (Legal Basis) が明確か
2. 正当な目的 (Legitimate Purpose) があるか
3. 必要性・比例性 (Necessity & Proportionality) があるか（過度な広汎性がないか）

【出力形式】
- 一人称は「茜」、語尾は関西弁（「〜やで」「〜やんな」）。
- 各項目を5点満点で評価し、その理由を述べる。
- 最後に「妥当」「問題あり」「要検討」のいずれかで総合判定する。
- 難しい法律用語はなるべく噛み砕いて説明する。
"""

# =========================
# メイン Bot クラス
# =========================

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

    # ★ GPT-5.1 対応のモデル判定
    def is_reasoning_model(self) -> bool:
        """
        GPT-5.1, o1, o3 などの 'Reasoning' (思考) 能力を持つモデルか判定。
        これらは max_tokens ではなく max_completion_tokens を使用する傾向がある。
        """
        m = self.config.GPT_MODEL.lower()
        return any(k in m for k in ["gpt-5", "o1", "o3"])

    async def setup_hook(self):
        self.cleanup_old_data.start()
        self.update_stats.start()

    @tasks.loop(hours=24)
    async def cleanup_old_data(self):
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()
            cutoff = (datetime.now(JST) - timedelta(days=30)).isoformat()
            cursor.execute('DELETE FROM conversation_history WHERE timestamp < ?', (cutoff,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    @tasks.loop(minutes=30)
    async def update_stats(self):
        if not self.is_ready(): return
        try:
            conn = sqlite3.connect(self.config.DATABASE_NAME)
            cursor = conn.cursor()
            today = datetime.now(JST).strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(DISTINCT user_id) FROM usage_log WHERE date = ?', (today,))
            res = cursor.fetchone()
            count = res[0] if res else 0
            conn.close()
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"表現の自由 (今日:{count}人)"))
        except Exception as e:
            logger.error(f"Stats update error: {e}")

    async def on_ready(self):
        logger.info(f'茜ちゃん(GPT-5.1搭載) 起動！ {self.user}')
        print(f"Model: {self.config.GPT_MODEL}")

    async def on_message(self, message):
        if message.author.bot: return
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat_message(message)
        await self.process_commands(message)

    async def handle_chat_message(self, message):
        start_time = datetime.now()
        user_id = str(message.author.id)
        username = message.author.display_name

        self.stats['total_messages'] += 1
        self.stats['unique_users'].add(user_id)

        usage = self.db.get_user_usage_today(user_id, username)
        if usage >= self.config.DAILY_MESSAGE_LIMIT:
            await message.reply("今日の会話はここまでやで〜。また明日な！")
            return

        new_usage = self.db.increment_user_usage(user_id, username)

        try:
            async with message.channel.typing():
                content = re.sub(r'<@!?\d+>', '', message.content).strip()
                is_reg = self.analyzer.detect_regulation_question(content)

                if is_reg:
                    response = await self.handle_regulation_analysis(content, user_id, username)
                    self.stats['regulation_analyses'] += 1
                else:
                    response = await self.handle_normal_chat(content, user_id, username)

                await self.send_response(message, response, is_reg)
                
                ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self.db.save_conversation(user_id, content, response, is_reg, ms)

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error: {e}")
            await message.reply("ごめん、なんかエラー出てもうたわ💦")

    # ---------- GPT 呼び出し処理 (GPT-5.1 最適化) ----------

    async def handle_regulation_analysis(self, message: str, user_id: str, username: str) -> str:
        target = self.analyzer.extract_regulation_target(message)
        prompt = self.analyzer.create_analysis_prompt(message, target)
        
        # GPT-5.1 は複雑な分析で reasoning_effort="high" が有効
        return await self.call_gpt_with_retry(
            system_prompt=prompt,
            user_message=message,
            max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS,
            temperature=0.6,
            reasoning_effort="high" 
        )

    async def handle_normal_chat(self, message: str, user_id: str, username: str) -> str:
        prompt = f"あなたは「表自派茜」という元気な関西弁の女子高生です。ユーザー名: {username}。親しみを込めて、短めに返答してな。"
        
        # 通常会話は reasoning_effort="medium" (デフォルト) または "low" で十分
        return await self.call_gpt_with_retry(
            system_prompt=prompt,
            user_message=message,
            max_tokens=self.config.NORMAL_CHAT_MAX_TOKENS,
            temperature=0.8,
            reasoning_effort="medium"
        )

    async def call_gpt_with_retry(
        self, system_prompt: str, user_message: str, max_tokens: int = 1000,
        temperature: float = 0.8, reasoning_effort: str = "medium", max_retries: int = 3
    ) -> str:
        """
        GPT-5.1 対応: reasoning_effort と temperature の両立
        """
        is_reasoning = self.is_reasoning_model() # True for gpt-5.1

        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
                
                params = {
                    "model": self.config.GPT_MODEL,
                    "messages": messages,
                }

                if is_reasoning:
                    # GPT-5系 / o1系 は max_completion_tokens を使用
                    params["max_completion_tokens"] = max_tokens
                    params["reasoning_effort"] = reasoning_effort
                    
                    # ★重要: GPT-5.1 は reasoning モデルだが temperature (人格制御) をサポートする
                    # 一方、旧来の o1-preview 等は temperature 非対応の場合があるため条件分岐
                    if "gpt-5" in self.config.GPT_MODEL:
                        params["temperature"] = temperature
                else:
                    # 従来のモデル (gpt-4oなど)
                    params["max_tokens"] = max_tokens
                    params["temperature"] = temperature

                response = client.chat.completions.create(**params)
                
                # 分析スコア抽出などのため、テキストのみ返す
                return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"GPT Retry {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    # エラー時は簡易メッセージを返す（クラッシュさせない）
                    return "あかん、通信エラーや... ちょっと待ってからまた話しかけて！"
                await asyncio.sleep(2 ** attempt)

    # ---------- レスポンス送信 ----------

    async def send_response(self, message, response: str, is_regulation: bool = False):
        if is_regulation:
            # 分析結果は見やすくEmbedで
            embed = discord.Embed(title="📋 茜の分析結果 (GPT-5.1)", color=0xffd700, timestamp=datetime.now(JST))
            if len(response) > 4000: response = response[:4000] + "..."
            embed.description = response
            await message.reply(embed=embed)
        else:
            # 通常会話
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await message.channel.send(response[i:i+2000])
            else:
                await message.reply(response)

# =========================
# 実行ブロック
# =========================

if __name__ == '__main__':
    bot = AkaneBot()
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        logger.error("DISCORD_TOKEN が設定されてへんで！")
