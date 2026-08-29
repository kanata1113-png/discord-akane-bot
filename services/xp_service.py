from __future__ import annotations

from config import Config
from repositories.user_repository import UserRepository


class XPService:
    def __init__(self, users: UserRepository):
        self.users = users

    @staticmethod
    def required_xp(level: int) -> int:
        return UserRepository.required_xp(level)

    async def add_xp(
        self,
        user_id: int,
        amount: int = Config.XP_PER_MESSAGE,
    ) -> tuple[bool, int, int]:
        return await self.users.add_xp(user_id, amount)

    async def get_user_data(self, user_id: int) -> tuple[int, int]:
        return await self.users.get_user_data(user_id)

    async def get_level_info(self, user_id: int) -> dict:
        level, xp = await self.users.get_user_data(user_id)
        required = self.required_xp(level)
        remaining = max(0, required - xp)
        percentage = (xp / required * 100) if required > 0 else 0
        percentage = max(0.0, min(percentage, 100.0))
        return {
            "level": level,
            "xp": xp,
            "required_xp": required,
            "remaining_xp": remaining,
            "percentage": percentage,
        }

    async def get_leaderboard(self, limit: int = 30):
        return await self.users.get_leaderboard(limit)
