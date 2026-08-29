import aiosqlite

from datetime import datetime, timedelta
from typing import Optional

from config import Config, JST


class DatabaseManager:

    def __init__(
        self,
        db_path: str
    ):

        self.path = db_path

    # ==========================================================================
    # Database Init
    # ==========================================================================

    async def init(self):

        async with aiosqlite.connect(
            self.path
        ) as db:

            # ==================================================================
            # AI Usage
            # ==================================================================

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

            # ==================================================================
            # Starboard
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS starboard_log (
                    message_id INTEGER PRIMARY KEY
                )
                """
            )

            # ==================================================================
            # Guild Settings
            # ==================================================================

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

            # ==================================================================
            # Users
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
                """
            )

            # ==================================================================
            # Level Rewards
            # ==================================================================

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

            # ==================================================================
            # Reaction Roles
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER
                )
                """
            )

            # ==================================================================
            # NG Words
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS ng_words (
                    guild_id INTEGER,
                    word TEXT
                )
                """
            )

            # ==================================================================
            # Auto Replies
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_replies (
                    guild_id INTEGER,
                    trigger TEXT,
                    response TEXT
                )
                """
            )

            # ==================================================================
            # Reminder
            # ==================================================================

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

            # ==================================================================
            # Monthly Rules
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_rules (
                    guild_id INTEGER PRIMARY KEY,
                    rule_ch INTEGER,
                    target_ch INTEGER
                )
                """
            )

            # ==================================================================
            # AI Conversation Memory
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conversation_lookup
                ON conversation_history (
                    guild_id,
                    channel_id,
                    user_id,
                    id
                )
                """
            )

            # ==================================================================
            # V31 Tickets
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_ticket_user
                ON tickets (
                    guild_id,
                    user_id,
                    status
                )
                """
            )

            await db.commit()

    # ==========================================================================
    # DB Helpers
    # ==========================================================================

    async def _execute(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(
            self.path
        ) as db:

            await db.execute(
                query,
                params
            )

            await db.commit()

    async def _fetchone(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(
            self.path
        ) as db:

            cursor = await db.execute(
                query,
                params
            )

            return await cursor.fetchone()

    async def _fetchall(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(
            self.path
        ) as db:

            cursor = await db.execute(
                query,
                params
            )

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
            (
                guild_id,
            )
        )

        if current:

            await self._execute(
                f"""
                UPDATE guild_settings
                SET {col}=?
                WHERE guild_id=?
                """,
                (
                    val,
                    guild_id
                )
            )

        else:

            await self._execute(
                f"""
                INSERT INTO guild_settings
                (
                    guild_id,
                    {col}
                )
                VALUES (?, ?)
                """,
                (
                    guild_id,
                    val
                )
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
            (
                guild_id,
            )
        )

        return (
            result[0]
            if result
            else None
        )

    # ==========================================================================
    # XP / Level
    # ==========================================================================

    @staticmethod
    def required_xp(
        level: int
    ) -> int:

        return max(
            100,
            level * 100
        )

    async def add_xp(
        self,
        user_id: int,
        amount: int = Config.XP_PER_MESSAGE
    ) -> tuple[bool, int, int]:

        row = await self._fetchone(
            """
            SELECT
                xp,
                level
            FROM users
            WHERE user_id=?
            """,
            (
                user_id,
            )
        )

        if not row:

            level = 1
            xp = amount

            leveled_up = False

            while xp >= self.required_xp(
                level
            ):

                needed = self.required_xp(
                    level
                )

                xp -= needed

                level += 1

                leveled_up = True

            await self._execute(
                """
                INSERT INTO users
                (
                    user_id,
                    xp,
                    level
                )
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    xp,
                    level
                )
            )

            return (
                leveled_up,
                level,
                xp
            )

        xp, level = row

        xp += amount

        leveled_up = False

        while xp >= self.required_xp(
            level
        ):

            needed = self.required_xp(
                level
            )

            xp -= needed

            level += 1

            leveled_up = True

        await self._execute(
            """
            UPDATE users
            SET
                xp=?,
                level=?
            WHERE user_id=?
            """,
            (
                xp,
                level,
                user_id
            )
        )

        return (
            leveled_up,
            level,
            xp
        )

    async def get_user_data(
        self,
        user_id: int
    ):

        result = await self._fetchone(
            """
            SELECT
                level,
                xp
            FROM users
            WHERE user_id=?
            """,
            (
                user_id,
            )
        )

        return (
            result
            if result
            else (
                1,
                0
            )
        )

    async def get_level_info(
        self,
        user_id: int
    ):

        level, xp = await self.get_user_data(
            user_id
        )

        required = self.required_xp(
            level
        )

        remaining = max(
            0,
            required - xp
        )

        percentage = (
            xp / required * 100
            if required > 0
            else 0
        )

        percentage = max(
            0.0,
            min(
                percentage,
                100.0
            )
        )

        return {
            "level": level,
            "xp": xp,
            "required_xp": required,
            "remaining_xp": remaining,
            "percentage": percentage,
        }

    async def get_leaderboard(
        self,
        limit: int = 30
    ):

        return await self._fetchall(
            """
            SELECT
                user_id,
                level,
                xp
            FROM users
            ORDER BY
                level DESC,
                xp DESC
            LIMIT ?
            """,
            (
                limit,
            )
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
        ).strftime(
            "%Y-%m-%d"
        )

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

        count = (
            row[0]
            if row
            else 0
        )

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
                (
                    user_id,
                    date,
                    count
                )
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
            + timedelta(
                minutes=minutes
            )
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

    # ==========================================================================
    # AI Conversation Memory
    # ==========================================================================

    async def add_conversation_message(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        role: str,
        content: str
    ):

        if role not in {
            "user",
            "assistant",
        }:

            raise ValueError(
                "Invalid conversation role."
            )

        if not content:

            return

        content = content[:4000]

        created_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT INTO conversation_history
            (
                guild_id,
                channel_id,
                user_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                user_id,
                role,
                content,
                created_at
            )
        )

    async def get_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        limit: int = Config.MEMORY_MESSAGE_LIMIT
    ):

        limit = max(
            1,
            min(
                int(limit),
                100
            )
        )

        rows = await self._fetchall(
            """
            SELECT
                role,
                content
            FROM conversation_history
            WHERE guild_id=?
            AND channel_id=?
            AND user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                guild_id,
                channel_id,
                user_id,
                limit
            )
        )

        rows.reverse()

        return [
            {
                "role": role,
                "content": content
            }
            for role, content
            in rows
        ]

    async def count_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int
    ) -> int:

        row = await self._fetchone(
            """
            SELECT COUNT(*)
            FROM conversation_history
            WHERE guild_id=?
            AND channel_id=?
            AND user_id=?
            """,
            (
                guild_id,
                channel_id,
                user_id
            )
        )

        return (
            int(row[0])
            if row
            else 0
        )

    async def clear_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int
    ) -> int:

        count = await self.count_conversation_history(
            guild_id,
            channel_id,
            user_id
        )

        await self._execute(
            """
            DELETE FROM conversation_history
            WHERE guild_id=?
            AND channel_id=?
            AND user_id=?
            """,
            (
                guild_id,
                channel_id,
                user_id
            )
        )

        return count

    async def clear_all_user_history(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        row = await self._fetchone(
            """
            SELECT COUNT(*)
            FROM conversation_history
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        count = (
            int(row[0])
            if row
            else 0
        )

        await self._execute(
            """
            DELETE FROM conversation_history
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return count

    async def cleanup_old_conversations(
        self,
        days: int = Config.MEMORY_RETENTION_DAYS
    ) -> int:

        days = max(
            1,
            int(days)
        )

        cutoff = (
            datetime.now(JST)
            - timedelta(
                days=days
            )
        ).isoformat()

        row = await self._fetchone(
            """
            SELECT COUNT(*)
            FROM conversation_history
            WHERE created_at < ?
            """,
            (
                cutoff,
            )
        )

        count = (
            int(row[0])
            if row
            else 0
        )

        if count > 0:

            await self._execute(
                """
                DELETE FROM conversation_history
                WHERE created_at < ?
                """,
                (
                    cutoff,
                )
            )

        return count

    # ==========================================================================
    # V31 Ticket
    # ==========================================================================

    async def get_open_ticket(
        self,
        guild_id: int,
        user_id: int
    ):

        return await self._fetchone(
            """
            SELECT
                id,
                channel_id,
                category,
                created_at
            FROM tickets
            WHERE guild_id=?
            AND user_id=?
            AND status='open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                guild_id,
                user_id
            )
        )

    async def get_ticket_by_channel(
        self,
        channel_id: int
    ):

        return await self._fetchone(
            """
            SELECT
                id,
                guild_id,
                user_id,
                category,
                status,
                created_at,
                closed_at
            FROM tickets
            WHERE channel_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                channel_id,
            )
        )

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str
    ):

        existing = await self.get_open_ticket(
            guild_id,
            user_id
        )

        if existing:

            raise ValueError(
                "User already has an open ticket."
            )

        created_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT INTO tickets
            (
                guild_id,
                channel_id,
                user_id,
                category,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'open', ?)
            """,
            (
                guild_id,
                channel_id,
                user_id,
                category,
                created_at
            )
        )

    async def close_ticket(
        self,
        channel_id: int
    ):

        closed_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            UPDATE tickets
            SET
                status='closed',
                closed_at=?
            WHERE channel_id=?
            AND status='open'
            """,
            (
                closed_at,
                channel_id
            )
        )

    async def count_open_tickets(
        self,
        guild_id: int
    ) -> int:

        row = await self._fetchone(
            """
            SELECT COUNT(*)
            FROM tickets
            WHERE guild_id=?
            AND status='open'
            """,
            (
                guild_id,
            )
        )

        return (
            int(row[0])
            if row
            else 0
        )

    async def cleanup_missing_ticket(
        self,
        channel_id: int
    ):

        await self.close_ticket(
            channel_id
        )
