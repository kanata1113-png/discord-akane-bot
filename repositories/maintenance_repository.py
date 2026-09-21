from __future__ import annotations

from repositories.base import BaseRepository


class MaintenanceRepository(BaseRepository):
    """Persistence used by background maintenance loops."""

    async def list_due_reminders(self, now_iso: str):
        """Return due reminders without deleting them.

        Delivery is acknowledged separately after Discord confirms that the
        message was sent. This prevents transient Discord/network failures from
        silently losing a reminder.
        """
        return await self.store.fetchall(
            """
            SELECT id, user_id, channel_id, message
            FROM reminders
            WHERE end_time <= ?
            ORDER BY id
            """,
            (now_iso,),
        )

    async def delete_reminder(self, reminder_id: int) -> int:
        """Acknowledge a successfully delivered reminder."""
        return await self.store.execute(
            "DELETE FROM reminders WHERE id = ?",
            (reminder_id,),
        )

    async def claim_due_reminders(self, now_iso: str):
        """Compatibility alias for the former destructive claim API.

        The old implementation deleted rows before Discord delivery. During
        dogfood hardening this method intentionally becomes non-destructive so
        any remaining caller cannot lose reminders on a failed send.
        """
        return await self.list_due_reminders(now_iso)

    async def get_monthly_rules(self):
        return await self.store.fetchall(
            """
            SELECT rule_ch, target_ch
            FROM monthly_rules
            """
        )
