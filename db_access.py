from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite


SQLITE_BUSY_TIMEOUT_MS = 5000


class SQLiteStore:
    """Small database access layer shared by repositories.

    Phase 4 keeps the legacy DatabaseManager intact for compatibility. New
    repositories use this class so connection and transaction handling no
    longer needs to be duplicated in each domain object.

    Connections are configured conservatively for the single-file production
    database. A busy timeout reduces transient write-contention failures while
    preserving the existing database path and transaction semantics.
    """

    def __init__(self, db_path: str):
        self.path = db_path

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
            await db.execute("PRAGMA foreign_keys = ON")
            yield db

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.rowcount

    async def insert(self, query: str, params: tuple[Any, ...] = ()) -> int:
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return int(cursor.lastrowid or 0)

    async def fetchone(self, query: str, params: tuple[Any, ...] = ()):
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()):
        async with self.connection() as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with self.connection() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
