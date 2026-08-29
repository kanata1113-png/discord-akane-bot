from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

import aiosqlite


MigrationCallable = Callable[[aiosqlite.Connection], Awaitable[None]]


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: MigrationCallable


MIGRATION_TABLE = "schema_migrations"


async def _baseline_v34_schema(db: aiosqlite.Connection) -> None:
    """Adopt the already-deployed v34 schema without rewriting user data.

    DatabaseManager.init() remains responsible for creating the current baseline
    tables in Phase 3. This migration only records that the baseline has been
    reached. Future schema changes are added as new numbered migrations.
    """


MIGRATIONS = (
    Migration(
        version=1,
        name="baseline_v34_schema",
        apply=_baseline_v34_schema,
    ),
)

LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version


async def _ensure_migration_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


async def _get_applied_versions(db: aiosqlite.Connection) -> set[int]:
    cursor = await db.execute(
        f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version ASC"
    )
    rows = await cursor.fetchall()
    return {int(row[0]) for row in rows}


async def get_schema_version(db_path: str) -> int:
    """Return the highest applied migration version, or 0 if unversioned."""

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            """,
            (MIGRATION_TABLE,),
        )
        if await cursor.fetchone() is None:
            return 0

        cursor = await db.execute(
            f"SELECT COALESCE(MAX(version), 0) FROM {MIGRATION_TABLE}"
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def run_migrations(db_path: str) -> list[Migration]:
    """Apply all pending migrations in a single SQLite transaction.

    The runner never deletes or recreates the database. If any migration fails,
    the transaction is rolled back so its version is not recorded as applied.
    """

    applied_now: list[Migration] = []

    async with aiosqlite.connect(db_path) as db:
        try:
            await db.execute("BEGIN IMMEDIATE")
            await _ensure_migration_table(db)
            applied_versions = await _get_applied_versions(db)

            unknown_versions = {
                version
                for version in applied_versions
                if version > LATEST_SCHEMA_VERSION
            }
            if unknown_versions:
                raise RuntimeError(
                    "Database schema is newer than this application: "
                    f"{sorted(unknown_versions)}"
                )

            for migration in MIGRATIONS:
                if migration.version in applied_versions:
                    continue

                await migration.apply(db)
                await db.execute(
                    f"""
                    INSERT INTO {MIGRATION_TABLE}
                    (version, name, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        migration.version,
                        migration.name,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                applied_now.append(migration)

            await db.commit()

        except Exception:
            await db.rollback()
            raise

    return applied_now
