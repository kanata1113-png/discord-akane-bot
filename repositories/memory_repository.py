from __future__ import annotations

from datetime import datetime, timedelta

from config import JST
from repositories.base import BaseRepository


class MemoryRepository(BaseRepository):
    async def add_message(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        role: str,
        content: str,
    ) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Invalid conversation role.")
        if not content:
            return

        await self.store.execute(
            """
            INSERT INTO conversation_history
            (guild_id, channel_id, user_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                user_id,
                role,
                content[:4000],
                datetime.now(JST).isoformat(),
            ),
        )

    async def get_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        limit: int,
    ):
        rows = await self.store.fetchall(
            """
            SELECT role, content
            FROM conversation_history
            WHERE guild_id=? AND channel_id=? AND user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, channel_id, user_id, limit),
        )
        return list(reversed(rows))

    async def forget_user(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int | None = None,
    ) -> None:
        if channel_id is None:
            await self.store.execute(
                "DELETE FROM conversation_history WHERE guild_id=? AND user_id=?",
                (guild_id, user_id),
            )
        else:
            await self.store.execute(
                """
                DELETE FROM conversation_history
                WHERE guild_id=? AND channel_id=? AND user_id=?
                """,
                (guild_id, channel_id, user_id),
            )

    async def cleanup_old(self, retention_days: int) -> int:
        cutoff = (datetime.now(JST) - timedelta(days=retention_days)).isoformat()
        return await self.store.execute(
            "DELETE FROM conversation_history WHERE created_at < ?",
            (cutoff,),
        )
