from __future__ import annotations

from database import DatabaseManager
from repositories.registry import RepositoryRegistry
from services.memory_service import MemoryService
from services.progress_service import ProgressService
from services.ticket_service import TicketService
from services.xp_service import XPService


class ServiceRegistry:
    def __init__(
        self,
        repositories: RepositoryRegistry,
        legacy_db: DatabaseManager,
    ):
        self.xp = XPService(repositories.users)
        self.memory = MemoryService(repositories.memory)
        self.tickets = TicketService(repositories.tickets)
        self.progress = ProgressService(legacy_db)
