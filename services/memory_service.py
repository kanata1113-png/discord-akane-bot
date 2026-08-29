from __future__ import annotations

from config import Config
from repositories.memory_repository import MemoryRepository


class MemoryService:
    def __init__(self, memory: MemoryRepository):
        self.memory = memory

    async def add_message(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        role: str,
        content: str,
    ) -> None:
        await self.memory.add_message(
            guild_id,
            channel_id,
            user_id,
            role,
            content,
        )

    async def get_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        limit: int = Config.MEMORY_MESSAGE_LIMIT,
    ) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        rows = await self.memory.get_history(
            guild_id,
            channel_id,
            user_id,
            limit,
        )
        return [
            {"role": role, "content": content}
            for role, content in rows
        ]

    async def count(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        row = await self.memory.store.fetchone(
            """
            SELECT COUNT(*)
            FROM conversation_history
            WHERE guild_id=? AND channel_id=? AND user_id=?
            """,
            (guild_id, channel_id, user_id),
        )
        return int(row[0]) if row else 0

    async def clear_channel(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        count = await self.count(guild_id, channel_id, user_id)
        await self.memory.forget_user(
            guild_id,
            user_id,
            channel_id=channel_id,
        )
        return count

    async def clear_all(self, guild_id: int, user_id: int) -> int:
        row = await self.memory.store.fetchone(
            """
            SELECT COUNT(*)
            FROM conversation_history
            WHERE guild_id=? AND user_id=?
            """,
            (guild_id, user_id),
        )
        count = int(row[0]) if row else 0
        await self.memory.forget_user(guild_id, user_id)
        return count

    async def cleanup_old(
        self,
        days: int = Config.MEMORY_RETENTION_DAYS,
    ) -> int:
        days = max(1, int(days))
        return await self.memory.cleanup_old(days)
