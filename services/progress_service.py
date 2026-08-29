from __future__ import annotations

from database import DatabaseManager


class ProgressService:
    """Bridge business-level progression operations during the v35 migration.

    Achievement/title/stat persistence still lives in the legacy manager in
    Phase 5. Callers can depend on this service now, and its storage can move to
    dedicated repositories later without changing Discord-facing code.
    """

    def __init__(self, legacy_db: DatabaseManager):
        self.legacy_db = legacy_db

    async def evaluate_unlocks(self, guild_id: int, user_id: int) -> dict:
        return await self.legacy_db.evaluate_progress_unlocks(guild_id, user_id)

    async def increment_ticket_count(self, guild_id: int, user_id: int) -> int:
        return await self.legacy_db.increment_ticket_count(guild_id, user_id)

    async def get_user_stats(self, guild_id: int, user_id: int):
        return await self.legacy_db.get_user_stats(guild_id, user_id)

    async def get_user_achievements(self, guild_id: int, user_id: int):
        return await self.legacy_db.get_user_achievements(guild_id, user_id)

    async def get_user_titles(self, guild_id: int, user_id: int):
        return await self.legacy_db.get_user_titles(guild_id, user_id)

    async def get_equipped_title(self, guild_id: int, user_id: int):
        return await self.legacy_db.get_equipped_title(guild_id, user_id)
