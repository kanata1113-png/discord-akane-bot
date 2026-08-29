import sqlite3

import pytest

import db_migrations
from database import DatabaseManager
from db_migrations import (
    LATEST_SCHEMA_VERSION,
    MIGRATION_TABLE,
    Migration,
    get_schema_version,
    run_migrations,
)


@pytest.mark.asyncio
async def test_unversioned_current_database_is_adopted_without_data_loss(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    await manager.add_xp(123, 150)

    assert await get_schema_version(str(db_path)) == 0

    applied = await run_migrations(str(db_path))

    assert [migration.version for migration in applied] == [1]
    assert await get_schema_version(str(db_path)) == LATEST_SCHEMA_VERSION

    with sqlite3.connect(db_path) as connection:
        user_row = connection.execute(
            "SELECT user_id, xp, level FROM users WHERE user_id=?",
            (123,),
        ).fetchone()
        migration_row = connection.execute(
            f"SELECT version, name FROM {MIGRATION_TABLE}"
        ).fetchone()

    assert user_row == (123, 50, 2)
    assert migration_row == (1, "baseline_v34_schema")


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()

    first = await run_migrations(str(db_path))
    second = await run_migrations(str(db_path))

    assert [migration.version for migration in first] == [1]
    assert second == []
    assert await get_schema_version(str(db_path)) == LATEST_SCHEMA_VERSION

    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            f"SELECT COUNT(*) FROM {MIGRATION_TABLE}"
        ).fetchone()[0]

    assert count == 1


@pytest.mark.asyncio
async def test_failed_migration_rolls_back_version_record(tmp_path, monkeypatch):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    await run_migrations(str(db_path))

    async def failing_migration(db):
        await db.execute(
            "CREATE TABLE should_rollback (id INTEGER PRIMARY KEY)"
        )
        raise RuntimeError("intentional migration failure")

    migration_v2 = Migration(
        version=2,
        name="intentional_failure",
        apply=failing_migration,
    )

    monkeypatch.setattr(
        db_migrations,
        "MIGRATIONS",
        db_migrations.MIGRATIONS + (migration_v2,),
    )
    monkeypatch.setattr(db_migrations, "LATEST_SCHEMA_VERSION", 2)

    with pytest.raises(RuntimeError, match="intentional migration failure"):
        await db_migrations.run_migrations(str(db_path))

    with sqlite3.connect(db_path) as connection:
        recorded_v2 = connection.execute(
            f"SELECT COUNT(*) FROM {MIGRATION_TABLE} WHERE version=2"
        ).fetchone()[0]
        rolled_back_table = connection.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type='table' AND name='should_rollback'
            """
        ).fetchone()[0]

    assert recorded_v2 == 0
    assert rolled_back_table == 0


@pytest.mark.asyncio
async def test_newer_database_version_is_rejected(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    await run_migrations(str(db_path))

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f"""
            INSERT INTO {MIGRATION_TABLE} (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (999, "future_schema", "2099-01-01T00:00:00+00:00"),
        )
        connection.commit()

    with pytest.raises(RuntimeError, match="newer than this application"):
        await run_migrations(str(db_path))
