from __future__ import annotations

from datetime import datetime

from config import JST
from repositories.maintenance_repository import MaintenanceRepository


class MaintenanceService:
    def __init__(self, repository: MaintenanceRepository):
        self.repository = repository

    async def list_due_reminders(self):
        return await self.repository.list_due_reminders(
            datetime.now(JST).isoformat()
        )

    async def delete_reminder(self, reminder_id: int) -> int:
        return await self.repository.delete_reminder(reminder_id)

    async def claim_due_reminders(self):
        """Compatibility alias; retrieval is intentionally non-destructive."""
        return await self.list_due_reminders()

    async def get_monthly_rules(self):
        return await self.repository.get_monthly_rules()
