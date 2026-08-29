from __future__ import annotations

from config import Config
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    @staticmethod
    def required_xp(level: int) -> int:
        return max(100, level * 100)

    async def get_user_data(self, user_id: int) -> tuple[int, int]:
        row = await self.store.fetchone(
            "SELECT level, xp FROM users WHERE user_id=?",
            (user_id,),
        )
        return row if row else (1, 0)

    async def add_xp(
        self,
        user_id: int,
        amount: int = Config.XP_PER_MESSAGE,
    ) -> tuple[bool, int, int]:
        async with self.store.transaction() as db:
            cursor = await db.execute(
                "SELECT xp, level FROM users WHERE user_id=?",
                (user_id,),
            )
            row = await cursor.fetchone()

            if row:
                xp, level = int(row[0]), int(row[1])
            else:
                xp, level = 0, 1

            xp += amount
            leveled_up = False

            while xp >= self.required_xp(level):
                xp -= self.required_xp(level)
                level += 1
                leveled_up = True

            await db.execute(
                """
                INSERT INTO users (user_id, xp, level)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    xp=excluded.xp,
                    level=excluded.level
                """,
                (user_id, xp, level),
            )

        return leveled_up, level, xp

    async def get_leaderboard(self, limit: int = 30):
        return await self.store.fetchall(
            """
            SELECT user_id, level, xp
            FROM users
            ORDER BY level DESC, xp DESC
            LIMIT ?
            """,
            (limit,),
        )
