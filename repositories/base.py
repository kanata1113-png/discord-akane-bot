from db_access import SQLiteStore


class BaseRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store
