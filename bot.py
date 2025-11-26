import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import os
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
import pytz
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

# =========================
# 0. 環境変数・ログ設定
# =========================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class OpenAIConfig:
    # ★ここに gpt-5.1 を指定
    GPT_MODEL = "gpt-5.1"

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

# =========================
# 1. Bot設定
# =========================
class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    
    if os.path.exists("/data"):
        DB_NAME = '/data/akane_mix.db'
    else:
        DB_NAME = 'akane_mix.db'

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

# =========================
# 2. データベース管理
# =========================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # バックアップコード由来
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT, date TEXT, count INTEGER DEFAULT 0, last_message_at TEXT, UNIQUE(user_id, date))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS conversation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, message TEXT, response TEXT, is_regulation_analysis BOOLEAN, timestamp TEXT, response_time_ms INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS regulation_analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, regulation_target TEXT, question TEXT, legal_basis_score INTEGER, legitimate_purpose_score INTEGER, proportionality_score INTEGER, overall_judgment TEXT, detailed_analysis TEXT, timestamp TEXT)''')
            # 汎用機能由来
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, autorole_id INTEGER, welcome_channel_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    async def get_user_usage_today(self, user_id: str, username: str = None) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            today = datetime.now(JST).strftime('%Y-%m-%d')
            cursor = await db.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
            result = await cursor.fetchone()
            if username and result:
                await db.execute('UPDATE usage_log SET username = ? WHERE user_id = ? AND date = ?', (username, user_id, today))
                await db.commit()
            return result[0] if result else 0

    async def increment_user_usage(self, user_id: str, username: str = None) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            today = datetime.now(JST).strftime('%Y-%m-%d')
            now = datetime.now(JST)
            try:
                await db.execute('INSERT INTO usage_log (user_id, username, date, count, last_message_at) VALUES (?, ?, ?, 1, ?)', (user_id, username, today, now.isoformat()))
                new_count = 1
            except aiosqlite.IntegrityError:
                await db.execute('UPDATE usage_log SET count = count + 1, last_message_at = ?, username = COALESCE(?, username) WHERE user_id = ? AND date = ?', (now.isoformat(), username, user_id, today))
                cursor = await db.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
                row = await cursor.fetchone()
                new_count = row[0]
            await db.commit()
            return new_count

    async def save_conversation(self, user_id: str, message: str, response: str, is_regulation: bool, response_time_ms: int):
        async with aiosqlite.connect(self.db_name) as db:
            now = datetime.now(JST)
            await db.execute('INSERT INTO conversation_history (user_id, message, response, is_regulation_analysis, response_time_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?)', (user_id, message, response, is_regulation, response_time_ms, now.isoformat()))
            await db.commit()

    async def save_regulation_analysis(self, user_id: str, target: str, question: str, scores: Dict[str, int], judgment: str, analysis: str):
        async with aiosqlite.connect(self.db_name) as db:
            now = datetime.now(JST)
            await db.execute('INSERT INTO regulation_analysis (user_id, regulation_target, question, legal_basis_score, legitimate_purpose_score, proportionality_score, overall_judgment, detailed_analysis, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (user_id, target, question, scores.get('legal', 0), scores.get('purpose', 0), scores.get('proportion', 0), judgment, analysis, now.isoformat()))
            await db.commit()

# =========================
# 3. 表現規制分析ロジック
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
        patterns = [r'([^。！？\n]+?)への?(?:表現)?規制', r'([^。！？\n]+?)を?規制', r'([^。！？\n]+?)について.*規制']
        for pattern in patterns:
            m = re.search(pattern, message)
            if m:
                target = m.group(1).strip()
                if len(target) > 1: return target
        return "対象の表現"

    def create_analysis_prompt(self, question: str, target: str) -> str:
        return f"""あなたは表現の自由の専門家である関西弁の女子高生「表自派茜」です。
以下の表現規制について、憲法学の厳格審査基準に従って詳細分析してください。

【分析対象】
規制対象: {target}
質問内容: {question}

【審査フレームワーク】
1. 法律による根拠 (Legal Basis)
2. 正当な目的 (Legitimate Purpose)
3. 必要性・比例性 (Necessity & Proportionality)

【回答条件】
- 一人称は必ず「茜」
- 自然な関西弁
- 各項目ごとに点数(1-5)と理由
- 最終判断（妥当 / 要改善 / 問題あり）
"""

# =========================
# 4. メイン Bot クラス
# =========================
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=['!', '！'], intents=intents, help_command=None)
        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DB_NAME)
        self.analyzer = ExpressionRegulationAnalyzer()
        self.start_time = datetime.now(JST)
        self.stats = {'total_messages': 0, 'regulation_analyses': 0, 'unique_users': set(), 'errors': 0}

    async def setup_hook(self):
        await self.db.init_database()
        self.cleanup_old_data.start()
        self.update_stats.start()
        self.add_view(ScheduleView())
        self.add_view(TicketCreateView())

    @tasks.loop(hours=24)
    async def cleanup_old_data(self):
        try:
            async with aiosqlite.connect(self.config.DB_NAME) as db:
                cutoff = (datetime.now(JST) - timedelta(days=30)).isoformat()
                await db.execute('DELETE FROM conversation_history WHERE timestamp < ?', (cutoff,))
                await db.commit()
        except Exception as e:
            logger.error(f"Cleanup Error: {e}")

    @tasks.loop(minutes=30)
    async def update_stats(self):
        if not self.is_ready(): return
        try:
            async with aiosqlite.connect(self.config.DB_NAME) as db:
                today = datetime.now(JST).strftime('%Y-%m-%d')
                cursor = await db.execute('SELECT COUNT(DISTINCT user_id) FROM usage_log WHERE date = ?', (today,))
                row = await cursor.fetchone()
                active = row[0] if row else 0
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"表現の自由 ({active}人)"))
        except Exception as e:
            logger.error(f"Stats Error: {e}")

    async def on_ready(self):
        logger.info(f'茜ちゃん起動！ {self.user}')
        print(f"Model: {self.config.GPT_MODEL}")
        try:
            await self.tree.sync()
            logger.info("Commands Synced")
        except Exception as e:
            logger.error(f"Sync Error: {e}")

    async def on_message(self, message):
        if message.author.bot: return
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat_message(message)
        if message.guild:
            await self.handle_xp(message)
        await self.process_commands(message)

    async def handle_xp(self, message):
        async with aiosqlite.connect(self.config.DB_NAME) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
            row = await cursor.fetchone()
            if row:
                xp, level = row
                xp += 10
                if xp >= level * 100:
                    xp = 0
                    level += 1
                    await message.channel.send(f"🎉 {message.author.mention} Level Up! -> {level}")
                await db.execute("
