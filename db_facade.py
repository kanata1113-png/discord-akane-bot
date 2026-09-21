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

    async def get_native_ticket(self, channel_id: int):
        return await self.services.tickets.get_native_ticket(channel_id)

    async def reserve_ticket_number(self, guild_id: int) -> int:
        return await self.services.tickets.reserve_ticket_number(guild_id)

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
        *,
        ticket_number: int | None = None,
        subject: str | None = None,
    ):
        return await self.services.tickets.create_ticket(
            guild_id,
            channel_id,
            user_id,
            category,
            ticket_number=ticket_number,
            subject=subject,
        )

    async def close_ticket(self, channel_id: int):
        return await self.services.tickets.close_ticket(channel_id)

    async def reopen_ticket(self, channel_id: int):
        return await self.services.tickets.reopen_ticket(channel_id)

    async def claim_ticket(self, channel_id: int, user_id: int | None):
        return await self.services.tickets.claim_ticket(channel_id, user_id)

    async def mark_ticket_deleted(self, channel_id: int):
        return await self.services.tickets.mark_ticket_deleted(channel_id)

    async def get_ticket_settings(self, guild_id: int):
        return await self.services.tickets.get_ticket_settings(guild_id)

    async def set_ticket_category(self, guild_id: int, category_id: int | None):
        return await self.services.tickets.set_ticket_category(guild_id, category_id)

    async def set_ticket_staff_role(self, guild_id: int, role_id: int | None):
        return await self.services.tickets.set_staff_role(guild_id, role_id)

    async def add_ticket_member(self, ticket_id: int, user_id: int):
        return await self.services.tickets.add_ticket_member(ticket_id, user_id)

    async def remove_ticket_member(self, ticket_id: int, user_id: int):
        return await self.services.tickets.remove_ticket_member(ticket_id, user_id)

    async def list_ticket_members(self, ticket_id: int):
        return await self.services.tickets.list_ticket_members(ticket_id)

    async def audit_ticket(
        self,
        *,
        ticket_id: int | None,
        guild_id: int,
        channel_id: int | None,
        actor_id: int | None,
        action: str,
        detail: str | None = None,
    ):
        return await self.services.tickets.audit(
            ticket_id=ticket_id,
            guild_id=guild_id,
            channel_id=channel_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
        )

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
