from __future__ import annotations

from config import Config
from database import DatabaseManager
from services.registry import ServiceRegistry


class DatabaseFacade:
    """Compatibility bridge from legacy bot.db calls to v35 services.

    Existing Cog/View call sites keep using ``bot.db`` during the staged
    migration. Selected stable public methods are routed through Service and
    Repository layers; everything else delegates to the legacy manager.
    """

    def __init__(self, legacy: DatabaseManager, services: ServiceRegistry):
        self.legacy = legacy
        self.services = services
        self.path = legacy.path

    def __getattr__(self, name):
        return getattr(self.legacy, name)

    async def init(self):
        return await self.legacy.init()

    @staticmethod
    def required_xp(level: int) -> int:
        return max(100, level * 100)

    async def add_xp(
        self,
        user_id: int,
        amount: int = Config.XP_PER_MESSAGE,
    ):
        return await self.services.xp.add_xp(user_id, amount)

    async def get_user_data(self, user_id: int):
        return await self.services.xp.get_user_data(user_id)

    async def get_level_info(self, user_id: int):
        return await self.services.xp.get_level_info(user_id)

    async def get_leaderboard(self, limit: int = 30):
        return await self.services.xp.get_leaderboard(limit)

    async def add_conversation_message(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        role: str,
        content: str,
    ):
        return await self.services.memory.add_message(
            guild_id,
            channel_id,
            user_id,
            role,
            content,
        )

    async def get_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        limit: int = Config.MEMORY_MESSAGE_LIMIT,
    ):
        return await self.services.memory.get_history(
            guild_id,
            channel_id,
            user_id,
            limit,
        )

    async def count_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        return await self.services.memory.count(guild_id, channel_id, user_id)

    async def clear_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        return await self.services.memory.clear_channel(
            guild_id,
            channel_id,
            user_id,
        )

    async def clear_all_user_history(self, guild_id: int, user_id: int) -> int:
        return await self.services.memory.clear_all(guild_id, user_id)

    async def cleanup_old_conversations(
        self,
        days: int = Config.MEMORY_RETENTION_DAYS,
    ) -> int:
        return await self.services.memory.cleanup_old(days)

    async def get_open_ticket(self, guild_id: int, user_id: int):
        return await self.services.tickets.get_open_ticket(guild_id, user_id)

    async def get_ticket_by_channel(self, channel_id: int):
        return await self.services.tickets.get_ticket_by_channel(channel_id)

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
    ):
        return await self.services.tickets.create_ticket(
            guild_id,
            channel_id,
            user_id,
            category,
        )

    async def close_ticket(self, channel_id: int):
        return await self.services.tickets.close_ticket(channel_id)

    async def count_open_tickets(self, guild_id: int) -> int:
        return await self.services.tickets.count_open_tickets(guild_id)

    async def cleanup_missing_ticket(self, channel_id: int):
        return await self.services.tickets.cleanup_missing_ticket(channel_id)

    async def increment_ticket_count(self, guild_id: int, user_id: int) -> int:
        return await self.services.progress.increment_ticket_count(guild_id, user_id)

    async def evaluate_progress_unlocks(self, guild_id: int, user_id: int):
        return await self.services.progress.evaluate_unlocks(guild_id, user_id)

    async def get_user_stats(self, guild_id: int, user_id: int):
        return await self.services.progress.get_user_stats(guild_id, user_id)

    async def get_user_achievements(self, guild_id: int, user_id: int):
        return await self.services.progress.get_user_achievements(guild_id, user_id)

    async def get_user_titles(self, guild_id: int, user_id: int):
        return await self.services.progress.get_user_titles(guild_id, user_id)

    async def get_equipped_title(self, guild_id: int, user_id: int):
        return await self.services.progress.get_equipped_title(guild_id, user_id)
