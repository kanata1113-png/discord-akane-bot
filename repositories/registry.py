from __future__ import annotations

from db_access import SQLiteStore
from repositories.guild_repository import GuildRepository
from repositories.maintenance_repository import MaintenanceRepository
from repositories.memory_repository import MemoryRepository
from repositories.ranking_repository import RankingRepository
from repositories.ticket_repository import TicketRepository
from repositories.user_repository import UserRepository


class RepositoryRegistry:
    """Container for domain repositories sharing one database path."""

    def __init__(self, db_path: str):
        self.store = SQLiteStore(db_path)
        self.guilds = GuildRepository(self.store)
        self.users = UserRepository(self.store)
        self.tickets = TicketRepository(self.store)
        self.memory = MemoryRepository(self.store)
        self.rankings = RankingRepository(self.store)
        self.maintenance = MaintenanceRepository(self.store)
