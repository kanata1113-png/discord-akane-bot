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
            # Users / XP
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
            # Reminders
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

            # ==================================================================
            # V32 User Stats
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_stats (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    ai_chat_count INTEGER DEFAULT 0,
                    fortune_count INTEGER DEFAULT 0,
                    ticket_count INTEGER DEFAULT 0,
                    first_seen TEXT,
                    last_seen TEXT,
                    PRIMARY KEY (
                        guild_id,
                        user_id
                    )
                )
                """
            )

            # ==================================================================
            # V32 Achievements
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_achievements (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    achievement_key TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    PRIMARY KEY (
                        guild_id,
                        user_id,
                        achievement_key
                    )
                )
                """
            )

            # ==================================================================
            # V32 Titles
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_titles (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    title_key TEXT NOT NULL,
                    equipped INTEGER DEFAULT 0,
                    unlocked_at TEXT NOT NULL,
                    PRIMARY KEY (
                        guild_id,
                        user_id,
                        title_key
                    )
                )
                """
            )

            # ==================================================================
            # V32 Daily Fortune
            # ==================================================================

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_fortunes (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    fortune_date TEXT NOT NULL,
                    fortune_key TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (
                        guild_id,
                        user_id,
                        fortune_date
                    )
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

    # ==========================================================================
    # V32 User Stats
    # ==========================================================================

    async def ensure_user_stats(
        self,
        guild_id: int,
        user_id: int
    ):

        now = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT OR IGNORE INTO user_stats
            (
                guild_id,
                user_id,
                message_count,
                ai_chat_count,
                fortune_count,
                ticket_count,
                first_seen,
                last_seen
            )
            VALUES (?, ?, 0, 0, 0, 0, ?, ?)
            """,
            (
                guild_id,
                user_id,
                now,
                now
            )
        )

    async def increment_message_count(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        await self.ensure_user_stats(
            guild_id,
            user_id
        )

        now = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            UPDATE user_stats
            SET
                message_count=message_count+1,
                last_seen=?
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                now,
                guild_id,
                user_id
            )
        )

        row = await self._fetchone(
            """
            SELECT message_count
            FROM user_stats
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return int(
            row[0]
        )

    async def increment_ai_chat_count(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        await self.ensure_user_stats(
            guild_id,
            user_id
        )

        await self._execute(
            """
            UPDATE user_stats
            SET ai_chat_count=ai_chat_count+1
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        row = await self._fetchone(
            """
            SELECT ai_chat_count
            FROM user_stats
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return int(
            row[0]
        )

    async def increment_fortune_count(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        await self.ensure_user_stats(
            guild_id,
            user_id
        )

        await self._execute(
            """
            UPDATE user_stats
            SET fortune_count=fortune_count+1
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        row = await self._fetchone(
            """
            SELECT fortune_count
            FROM user_stats
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return int(
            row[0]
        )

    async def increment_ticket_count(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        await self.ensure_user_stats(
            guild_id,
            user_id
        )

        await self._execute(
            """
            UPDATE user_stats
            SET ticket_count=ticket_count+1
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        row = await self._fetchone(
            """
            SELECT ticket_count
            FROM user_stats
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return int(
            row[0]
        )

    async def get_user_stats(
        self,
        guild_id: int,
        user_id: int
    ):

        await self.ensure_user_stats(
            guild_id,
            user_id
        )

        row = await self._fetchone(
            """
            SELECT
                message_count,
                ai_chat_count,
                fortune_count,
                ticket_count,
                first_seen,
                last_seen
            FROM user_stats
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return {
            "message_count": int(
                row[0]
            ),
            "ai_chat_count": int(
                row[1]
            ),
            "fortune_count": int(
                row[2]
            ),
            "ticket_count": int(
                row[3]
            ),
            "first_seen": row[4],
            "last_seen": row[5],
        }

    # ==========================================================================
    # V32 Achievements
    # ==========================================================================

    async def has_achievement(
        self,
        guild_id: int,
        user_id: int,
        achievement_key: str
    ) -> bool:

        row = await self._fetchone(
            """
            SELECT 1
            FROM user_achievements
            WHERE guild_id=?
            AND user_id=?
            AND achievement_key=?
            """,
            (
                guild_id,
                user_id,
                achievement_key
            )
        )

        return row is not None

    async def unlock_achievement(
        self,
        guild_id: int,
        user_id: int,
        achievement_key: str
    ) -> bool:

        if achievement_key not in Config.ACHIEVEMENTS:

            raise ValueError(
                f"Unknown achievement: {achievement_key}"
            )

        if await self.has_achievement(
            guild_id,
            user_id,
            achievement_key
        ):

            return False

        unlocked_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT OR IGNORE INTO user_achievements
            (
                guild_id,
                user_id,
                achievement_key,
                unlocked_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                achievement_key,
                unlocked_at
            )
        )

        return True

    async def get_user_achievements(
        self,
        guild_id: int,
        user_id: int
    ):

        return await self._fetchall(
            """
            SELECT
                achievement_key,
                unlocked_at
            FROM user_achievements
            WHERE guild_id=?
            AND user_id=?
            ORDER BY unlocked_at ASC
            """,
            (
                guild_id,
                user_id
            )
        )

    async def count_user_achievements(
        self,
        guild_id: int,
        user_id: int
    ) -> int:

        row = await self._fetchone(
            """
            SELECT COUNT(*)
            FROM user_achievements
            WHERE guild_id=?
            AND user_id=?
            """,
            (
                guild_id,
                user_id
            )
        )

        return (
            int(row[0])
            if row
            else 0
        )

    # ==========================================================================
    # V32 Titles
    # ==========================================================================

    async def has_title(
        self,
        guild_id: int,
        user_id: int,
        title_key: str
    ) -> bool:

        row = await self._fetchone(
            """
            SELECT 1
            FROM user_titles
            WHERE guild_id=?
            AND user_id=?
            AND title_key=?
            """,
            (
                guild_id,
                user_id,
                title_key
            )
        )

        return row is not None

    async def unlock_title(
        self,
        guild_id: int,
        user_id: int,
        title_key: str
    ) -> bool:

        if title_key not in Config.TITLES:

            raise ValueError(
                f"Unknown title: {title_key}"
            )

        if await self.has_title(
            guild_id,
            user_id,
            title_key
        ):

            return False

        unlocked_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT OR IGNORE INTO user_titles
            (
                guild_id,
                user_id,
                title_key,
                equipped,
                unlocked_at
            )
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                guild_id,
                user_id,
                title_key,
                unlocked_at
            )
        )

        # 初称号なら自動装備
        equipped = await self.get_equipped_title(
            guild_id,
            user_id
        )

        if equipped is None:

            await self.set_equipped_title(
                guild_id,
                user_id,
                title_key
            )

        return True

    async def get_user_titles(
        self,
        guild_id: int,
        user_id: int
    ):

        return await self._fetchall(
            """
            SELECT
                title_key,
                equipped,
                unlocked_at
            FROM user_titles
            WHERE guild_id=?
            AND user_id=?
            ORDER BY unlocked_at ASC
            """,
            (
                guild_id,
                user_id
            )
        )

    async def get_equipped_title(
        self,
        guild_id: int,
        user_id: int
    ):

        row = await self._fetchone(
            """
            SELECT title_key
            FROM user_titles
            WHERE guild_id=?
            AND user_id=?
            AND equipped=1
            LIMIT 1
            """,
            (
                guild_id,
                user_id
            )
        )

        return (
            row[0]
            if row
            else None
        )

    async def set_equipped_title(
        self,
        guild_id: int,
        user_id: int,
        title_key: str
    ):

        if not await self.has_title(
            guild_id,
            user_id,
            title_key
        ):

            raise ValueError(
                "Title is not unlocked."
            )

        async with aiosqlite.connect(
            self.path
        ) as db:

            await db.execute(
                """
                UPDATE user_titles
                SET equipped=0
                WHERE guild_id=?
                AND user_id=?
                """,
                (
                    guild_id,
                    user_id
                )
            )

            await db.execute(
                """
                UPDATE user_titles
                SET equipped=1
                WHERE guild_id=?
                AND user_id=?
                AND title_key=?
                """,
                (
                    guild_id,
                    user_id,
                    title_key
                )
            )

            await db.commit()

    # ==========================================================================
    # V32 Fortune
    # ==========================================================================

    async def get_today_fortune(
        self,
        guild_id: int,
        user_id: int
    ):

        today = datetime.now(
            JST
        ).strftime(
            "%Y-%m-%d"
        )

        return await self._fetchone(
            """
            SELECT
                fortune_key,
                score
            FROM daily_fortunes
            WHERE guild_id=?
            AND user_id=?
            AND fortune_date=?
            """,
            (
                guild_id,
                user_id,
                today
            )
        )

    async def save_today_fortune(
        self,
        guild_id: int,
        user_id: int,
        fortune_key: str,
        score: int
    ):

        today = datetime.now(
            JST
        ).strftime(
            "%Y-%m-%d"
        )

        created_at = datetime.now(
            JST
        ).isoformat()

        await self._execute(
            """
            INSERT OR IGNORE INTO daily_fortunes
            (
                guild_id,
                user_id,
                fortune_date,
                fortune_key,
                score,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                user_id,
                today,
                fortune_key,
                int(score),
                created_at
            )
        )

    # ==========================================================================
    # V32 Automatic Unlock Evaluation
    # ==========================================================================

    async def evaluate_progress_unlocks(
        self,
        guild_id: int,
        user_id: int
    ) -> dict:

        stats = await self.get_user_stats(
            guild_id,
            user_id
        )

        level, _ = await self.get_user_data(
            user_id
        )

        new_achievements = []
        new_titles = []

        # ======================================================================
        # Achievement Conditions
        # ======================================================================

        achievement_conditions = [
            (
                "first_message",
                stats["message_count"] >= 1
            ),
            (
                "messages_100",
                stats["message_count"] >= 100
            ),
            (
                "messages_500",
                stats["message_count"] >= 500
            ),
            (
                "messages_1000",
                stats["message_count"] >= 1000
            ),
            (
                "level_5",
                level >= 5
            ),
            (
                "level_10",
                level >= 10
            ),
            (
                "level_20",
                level >= 20
            ),
            (
                "ai_10",
                stats["ai_chat_count"] >= 10
            ),
            (
                "ai_100",
                stats["ai_chat_count"] >= 100
            ),
            (
                "fortune_1",
                stats["fortune_count"] >= 1
            ),
            (
                "fortune_10",
                stats["fortune_count"] >= 10
            ),
            (
                "ticket_1",
                stats["ticket_count"] >= 1
            ),
        ]

        for (
            achievement_key,
            condition
        ) in achievement_conditions:

            if not condition:

                continue

            unlocked = await self.unlock_achievement(
                guild_id,
                user_id,
                achievement_key
            )

            if unlocked:

                new_achievements.append(
                    achievement_key
                )

        # ======================================================================
        # Title Conditions
        # ======================================================================

        title_conditions = [
            (
                "newcomer",
                stats["message_count"] >= 1
            ),
            (
                "regular",
                stats["message_count"] >= 100
            ),
            (
                "talkative",
                stats["message_count"] >= 500
            ),
            (
                "veteran",
                stats["message_count"] >= 1000
            ),
            (
                "level5",
                level >= 5
            ),
            (
                "level10",
                level >= 10
            ),
            (
                "level20",
                level >= 20
            ),
            (
                "ai_friend",
                stats["ai_chat_count"] >= 10
            ),
            (
                "ai_partner",
                stats["ai_chat_count"] >= 100
            ),
            (
                "supporter",
                stats["ticket_count"] >= 1
            ),
            (
                "lucky",
                stats["fortune_count"] >= 10
            ),
        ]

        for (
            title_key,
            condition
        ) in title_conditions:

            if not condition:

                continue

            unlocked = await self.unlock_title(
                guild_id,
                user_id,
                title_key
            )

            if unlocked:

                new_titles.append(
                    title_key
                )

        return {
            "achievements": new_achievements,
            "titles": new_titles,
        }
