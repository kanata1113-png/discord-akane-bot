from __future__ import annotations

from datetime import datetime

from config import JST
from repositories.maintenance_repository import MaintenanceRepository


class MaintenanceService:
    def __init__(self, repository: MaintenanceRepository):
        self.repository = repository

    async def claim_due_reminders(self):
        return await self.repository.claim_due_reminders(
            datetime.now(JST).isoformat()
        )

    async def get_monthly_rules(self):
        return await self.repository.get_monthly_rules()
