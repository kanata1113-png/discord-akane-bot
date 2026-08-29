import aiosqlite
from datetime import datetime, timedelta
from typing import Optional

from config import Config, JST


class DatabaseManager:

    def __init__(self, db_path: str):
        self.path = db_path

    # ==========================================================================
    # 初期化
    # ==========================================================================

    async def init(self):

        async with aiosqlite.connect(self.path) as db:

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_log (
                    user_id TEXT,
                    date TEXT,
                    count INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS starboard_log (
                    message_id INTEGER PRIMARY KEY
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_ch INTEGER,
                    log_ch INTEGER,
                    starboard_ch INTEGER,
                    auto_chat_ch INTEGER
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS level_rewards (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY(guild_id, level)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS ng_words (
                    guild_id INTEGER,
                    word TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_replies (
                    guild_id INTEGER,
                    trigger TEXT,
                    response TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    message TEXT,
                    end_time TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_rules (
                    guild_id INTEGER PRIMARY KEY,
                    rule_ch INTEGER,
                    target_ch INTEGER
                )
                """
            )

            await db.commit()

    # ==========================================================================
    # Helper
    # ==========================================================================

    async def _execute(self, query, params=()):

        async with aiosqlite.connect(self.path) as db:

            await db.execute(query, params)
            await db.commit()

    async def _fetchone(self, query, params=()):

        async with aiosqlite.connect(self.path) as db:

            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def _fetchall(self, query, params=()):

        async with aiosqlite.connect(self.path) as db:

            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    # ==========================================================================
    # Guild Config
    # ==========================================================================

    async def set_config(
        self,
        guild_id: int,
        col: str,
        val: int
    ):

        allowed_columns = {
            "welcome_ch",
            "log_ch",
            "starboard_ch",
            "auto_chat_ch",
        }

        if col not in allowed_columns:
            raise ValueError(
                f"Invalid guild config column: {col}"
            )

        current = await self._fetchone(
            """
            SELECT guild_id
            FROM guild_settings
            WHERE guild_id=?
            """,
            (guild_id,)
        )

        if current:

            await self._execute(
                f"""
                UPDATE guild_settings
                SET {col}=?
                WHERE guild_id=?
                """,
                (val, guild_id)
            )

        else:

            await self._execute(
                f"""
                INSERT INTO guild_settings
                (guild_id, {col})
                VALUES (?, ?)
                """,
                (guild_id, val)
            )

    async def get_config(
        self,
        guild_id: int,
        col: str
    ) -> Optional[int]:

        allowed_columns = {
            "welcome_ch",
            "log_ch",
            "starboard_ch",
            "auto_chat_ch",
        }

        if col not in allowed_columns:
            raise ValueError(
                f"Invalid guild config column: {col}"
            )

        result = await self._fetchone(
            f"""
            SELECT {col}
            FROM guild_settings
            WHERE guild_id=?
            """,
            (guild_id,)
        )

        return result[0] if result else None

    # ==========================================================================
    # XP
    # ==========================================================================

    async def add_xp(
        self,
        user_id: int,
        amount: int = 10
    ) -> bool:

        row = await self._fetchone(
            """
            SELECT xp, level
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        if row:

            xp, level = row

            xp += amount

            leveled_up = False

            # v28ではv27仕様をそのまま維持
            if xp >= level * 100:

                xp = 0
                level += 1
                leveled_up = True

            await self._execute(
                """
                UPDATE users
                SET xp=?, level=?
                WHERE user_id=?
                """,
                (
                    xp,
                    level,
                    user_id
                )
            )

            return leveled_up

        await self._execute(
            """
            INSERT INTO users
            (user_id, xp, level)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                amount,
                1
            )
        )

        return False

    async def get_user_data(
        self,
        user_id: int
    ):

        result = await self._fetchone(
            """
            SELECT level, xp
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        return result if result else (1, 0)

    async def get_leaderboard(
        self,
        limit: int = 30
    ):

        return await self._fetchall(
            """
            SELECT user_id, level, xp
            FROM users
            ORDER BY level DESC, xp DESC
            LIMIT ?
            """,
            (limit,)
        )

    # ==========================================================================
    # Daily AI Limit
    # ==========================================================================

    async def check_daily_limit(
        self,
        user_id: str
    ) -> bool:

        today = datetime.now(
            JST
        ).strftime("%Y-%m-%d")

        row = await self._fetchone(
            """
            SELECT count
            FROM usage_log
            WHERE user_id=?
            AND date=?
            """,
            (
                user_id,
                today
            )
        )

        count = row[0] if row else 0

        if count >= Config.DAILY_LIMIT:
            return False

        if row:

            await self._execute(
                """
                UPDATE usage_log
                SET count=count+1
                WHERE user_id=?
                AND date=?
                """,
                (
                    user_id,
                    today
                )
            )

        else:

            await self._execute(
                """
                INSERT INTO usage_log
                (user_id, date, count)
                VALUES (?, ?, 1)
                """,
                (
                    user_id,
                    today
                )
            )

        return True

    # ==========================================================================
    # Reminder
    # ==========================================================================

    async def add_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        minutes: int
    ):

        if minutes <= 0:
            raise ValueError(
                "minutes must be greater than 0"
            )

        end_time = (
            datetime.now(JST)
            + timedelta(minutes=minutes)
        ).isoformat()

        await self._execute(
            """
            INSERT INTO reminders
            (
                user_id,
                channel_id,
                message,
                end_time
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                channel_id,
                message,
                end_time
            )
        )
