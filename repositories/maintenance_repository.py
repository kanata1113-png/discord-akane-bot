from __future__ import annotations

from repositories.base import BaseRepository


class MaintenanceRepository(BaseRepository):
    """Persistence used by background maintenance loops."""

    async def claim_due_reminders(self, now_iso: str):
        """Atomically read and delete reminders due at or before ``now_iso``."""
        async with self.store.transaction() as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, channel_id, message
                FROM reminders
                WHERE end_time <= ?
                ORDER BY id
                """,
                (now_iso,),
            )
            rows = await cursor.fetchall()

            if rows:
                ids = [row[0] for row in rows]
                placeholders = ",".join("?" for _ in ids)
                await db.execute(
                    f"DELETE FROM reminders WHERE id IN ({placeholders})",
                    tuple(ids),
                )

            return rows

    async def get_monthly_rules(self):
        return await self.store.fetchall(
            """
            SELECT rule_ch, target_ch
            FROM monthly_rules
            """
        )
