import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import os
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta, time
import pytz
import re
import io
from collections import defaultdict, deque
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ==============================================================================
# 0. 環境変数・ログ・共通設定
# ==============================================================================
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
    GPT_MODEL = "gpt-5.1"

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    if os.path.exists("/data"):
        DB_NAME = '/data/akane_final_fixed.db'
    else:
        DB_NAME = 'akane_final_fixed.db'

    REGULATION_ANALYSIS_MAX_TOKENS = 2000
    NORMAL_CHAT_MAX_TOKENS = 800
    GPT_MODEL = OpenAIConfig.GPT_MODEL

    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '制限', '禁止', '表現の自由', '言論統制', '弾圧']
    QUESTION_KEYWORDS = ['妥当', '適切', '正しい', 'どう思う', '判断', '評価', '分析']

    FLAG_MAPPING = {
        "🇺🇸": "English", "🇬🇧": "English", "🇨🇦": "English",
        "🇯🇵": "Japanese", "🇨🇳": "Chinese", "🇰🇷": "Korean",
        "🇫🇷": "French", "🇩🇪": "German", "🇮🇹": "Italian",
        "🇪🇸": "Spanish", "🇷🇺": "Russian", "🇻🇳": "Vietnamese",
        "🇹🇭": "Thai", "🇮🇩": "Indonesian"
    }

# ==============================================================================
# 1. データベース管理
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # ログ・履歴
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, count INTEGER DEFAULT 0, UNIQUE(user_id, date))''')
            # 設定
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, autorole_id INTEGER, welcome_channel_id INTEGER, log_channel_id INTEGER, starboard_channel_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS monthly_settings (guild_id INTEGER PRIMARY KEY, rule_channel_id INTEGER, target_channel_id INTEGER)''')
            # ユーザー・その他
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS level_rewards (guild_id INTEGER, level INTEGER, role_id INTEGER, PRIMARY KEY(guild_id, level))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS ng_words (guild_id INTEGER, word TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, trigger TEXT, response TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, message TEXT, end_time TEXT)''')
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    # --- 設定系 ---
    async def set_channel_setting(self, guild_id: int, col_name: str, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", (guild_id,))
            if await cursor.fetchone():
                await db.execute(f"UPDATE settings SET {col_name} = ? WHERE guild_id = ?", (channel_id, guild_id))
            else:
                await db.execute(f"INSERT INTO settings (guild_id, {col_name}) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def get_channel_setting(self, guild_id: int, col_name: str) -> Optional[int]:
        async with aiosqlite.connect(self.db_name) as db:
            try:
                cursor = await db.execute(f"SELECT {col_name} FROM settings WHERE guild_id = ?", (guild_id,))
                row = await cursor.fetchone()
                return row[0] if row else None
            except: return None

    # --- 月次ルール通知設定 ---
    async def set_monthly_rule(self, guild_id: int, rule_ch_id: int, target_ch_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR REPLACE INTO monthly_settings (guild_id, rule_channel_id, target_channel_id) VALUES (?, ?, ?)", (guild_id, rule_ch_id, target_ch_id))
            await db.commit()

    async def get_all_monthly_settings(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id, rule_channel_id, target_channel_id FROM monthly_settings")
            return await cursor.fetchall()

    # --- XP系 ---
    async def add_xp(self, user_id: int, amount: int) -> tuple[int, int, bool]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                xp, level = row
                xp += amount
                if xp >= level * 100: xp = 0; level += 1; is_levelup = True
                else: is_levelup = False
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
            else:
                xp, level = amount, 1; is_levelup = False
                await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (user_id, xp, level))
            await db.commit()
            return xp, level, is_levelup

    # --- リアクションロール ---
    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)", (message_id, emoji, role_id))
