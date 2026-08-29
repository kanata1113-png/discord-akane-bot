from __future__ import annotations

from repositories.base import BaseRepository


class RankingRepository(BaseRepository):
    async def get_weekly_leaderboard(
        self,
        guild_id: int,
        week_key: str,
        limit: int = 10,
    ):
        return await self.store.fetchall(
            """
            SELECT user_id, xp
            FROM weekly_xp
            WHERE guild_id=? AND week_key=?
            ORDER BY xp DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, week_key, limit),
        )

    async def get_message_leaderboard(self, guild_id: int, limit: int = 10):
        return await self.store.fetchall(
            """
            SELECT user_id, message_count
            FROM user_stats
            WHERE guild_id=?
            ORDER BY message_count DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def get_ai_leaderboard(self, guild_id: int, limit: int = 10):
        return await self.store.fetchall(
            """
            SELECT user_id, ai_chat_count
            FROM user_stats
            WHERE guild_id=?
            ORDER BY ai_chat_count DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, limit),
        )

    async def get_achievement_leaderboard(
        self,
        guild_id: int,
        limit: int = 10,
    ):
        return await self.store.fetchall(
            """
            SELECT user_id, COUNT(*) AS achievement_count
            FROM user_achievements
            WHERE guild_id=?
            GROUP BY user_id
            ORDER BY achievement_count DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, limit),
        )
