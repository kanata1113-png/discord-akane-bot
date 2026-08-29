from __future__ import annotations

from datetime import datetime

from config import JST
from repositories.base import BaseRepository


class TicketRepository(BaseRepository):
    async def get_open_for_user(self, guild_id: int, user_id: int):
        return await self.store.fetchone(
            """
            SELECT id, channel_id, category, created_at
            FROM tickets
            WHERE guild_id=? AND user_id=? AND status='open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id, user_id),
        )

    async def get_by_channel(self, channel_id: int):
        return await self.store.fetchone(
            """
            SELECT id, guild_id, channel_id, user_id, category,
                   status, created_at, closed_at
            FROM tickets
            WHERE channel_id=?
            """,
            (channel_id,),
        )

    async def create(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
    ) -> int:
        created_at = datetime.now(JST).isoformat()
        return await self.store.insert(
            """
            INSERT INTO tickets
            (guild_id, channel_id, user_id, category, status, created_at)
            VALUES (?, ?, ?, ?, 'open', ?)
            """,
            (guild_id, channel_id, user_id, category, created_at),
        )

    async def close(self, channel_id: int) -> None:
        await self.store.execute(
            """
            UPDATE tickets
            SET status='closed', closed_at=?
            WHERE channel_id=? AND status='open'
            """,
            (datetime.now(JST).isoformat(), channel_id),
        )

    async def delete_by_channel(self, channel_id: int) -> None:
        await self.store.execute(
            "DELETE FROM tickets WHERE channel_id=?",
            (channel_id,),
        )
