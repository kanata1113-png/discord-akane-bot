from __future__ import annotations

from types import SimpleNamespace

import aiosqlite
import pytest

from app import build_discord_intents
from database import DatabaseManager
from db_access import SQLITE_BUSY_TIMEOUT_MS, SQLiteStore
from db_facade import DatabaseFacade
from db_migrations import run_migrations
from repositories.maintenance_repository import MaintenanceRepository


def test_discord_intents_are_explicit_and_support_current_features():
    intents = build_discord_intents()

    assert intents.guilds is True
    assert intents.messages is True
    assert intents.members is True
    assert intents.message_content is True
    assert intents.reactions is True
    assert intents.presences is False


@pytest.mark.asyncio
async def test_due_reminder_is_not_deleted_until_acknowledged(tmp_path):
    db_path = str(tmp_path / "reminders.db")
    store = SQLiteStore(db_path)
    repository = MaintenanceRepository(store)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                message TEXT,
                end_time TEXT
            )
            """
        )
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, message, end_time) "
            "VALUES (?, ?, ?, ?)",
            (1, 2, "keep me", "2026-01-01T00:00:00+09:00"),
        )
        await db.commit()

    rows = await repository.list_due_reminders("2026-12-31T00:00:00+09:00")
    assert len(rows) == 1

    async with aiosqlite.connect(db_path) as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM reminders")).fetchone())[0]
    assert count == 1

    await repository.delete_reminder(rows[0][0])

    async with aiosqlite.connect(db_path) as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM reminders")).fetchone())[0]
    assert count == 0


@pytest.mark.asyncio
async def test_sqlite_store_applies_busy_timeout(tmp_path):
    store = SQLiteStore(str(tmp_path / "store.db"))

    async with store.connection() as db:
        row = await (await db.execute("PRAGMA busy_timeout")).fetchone()

    assert row[0] == SQLITE_BUSY_TIMEOUT_MS


def test_database_facade_records_legacy_fallback_names_once():
    class Legacy:
        path = "example.db"

        def legacy_only(self):
            return "ok"

    facade = DatabaseFacade(Legacy(), SimpleNamespace())

    assert facade.legacy_only() == "ok"
    assert facade.legacy_only() == "ok"
    assert facade.get_legacy_fallbacks_seen() == ("legacy_only",)


@pytest.mark.asyncio
async def test_migrations_preserve_existing_production_state(tmp_path):
    db_path = str(tmp_path / "akane_v26.db")
    manager = DatabaseManager(db_path)
    await manager.init()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)",
            (1001, 4321, 17),
        )
        await db.execute(
            """
            INSERT INTO weekly_xp (guild_id, user_id, week_key, xp, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (2001, 1001, "2026-W38", 777, "2026-09-21T00:00:00+09:00"),
        )
        await db.execute(
            """
            INSERT INTO user_stats (
                guild_id, user_id, message_count, ai_chat_count,
                fortune_count, ticket_count, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (2001, 1001, 99, 11, 3, 2, "first", "last"),
        )
        await db.execute(
            """
            INSERT INTO reminders (user_id, channel_id, message, end_time)
            VALUES (?, ?, ?, ?)
            """,
            (1001, 3001, "important", "2026-12-01T12:00:00+09:00"),
        )
        await db.execute(
            """
            INSERT INTO tickets (
                guild_id, channel_id, user_id, category,
                status, created_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (2001, 4001, 1001, "general", "open", "created", None),
        )
        await db.commit()

    await run_migrations(db_path)

    async with aiosqlite.connect(db_path) as db:
        user = await (await db.execute(
            "SELECT xp, level FROM users WHERE user_id = ?", (1001,)
        )).fetchone()
        weekly = await (await db.execute(
            "SELECT xp FROM weekly_xp WHERE guild_id = ? AND user_id = ?",
            (2001, 1001),
        )).fetchone()
        stats = await (await db.execute(
            "SELECT message_count, ai_chat_count, fortune_count, ticket_count "
            "FROM user_stats WHERE guild_id = ? AND user_id = ?",
            (2001, 1001),
        )).fetchone()
        reminder = await (await db.execute(
            "SELECT message FROM reminders WHERE user_id = ?", (1001,)
        )).fetchone()
        ticket = await (await db.execute(
            "SELECT status, category FROM tickets WHERE channel_id = ?", (4001,)
        )).fetchone()

    assert user == (4321, 17)
    assert weekly == (777,)
    assert stats == (99, 11, 3, 2)
    assert reminder == ("important",)
    assert ticket == ("open", "general")
