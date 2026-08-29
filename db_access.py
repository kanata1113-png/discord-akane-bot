from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite


class SQLiteStore:
    """Small database access layer shared by repositories.

    Phase 4 keeps the legacy DatabaseManager intact for compatibility. New
    repositories use this class so connection and transaction handling no
    longer needs to be duplicated in each domain object.
    """

    def __init__(self, db_path: str):
        self.path = db_path

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.rowcount

    async def insert(self, query: str, params: tuple[Any, ...] = ()) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return int(cursor.lastrowid or 0)

    async def fetchone(self, query: str, params: tuple[Any, ...] = ()):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        async with aiosqlite.connect(self.path) as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
