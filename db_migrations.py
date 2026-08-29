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

REQUIRED_BASELINE_COLUMNS = {
    "usage_log": {"user_id", "date", "count"},
    "starboard_log": {"message_id"},
    "guild_settings": {
        "guild_id",
        "welcome_ch",
        "log_ch",
        "starboard_ch",
        "auto_chat_ch",
    },
    "users": {"user_id", "xp", "level"},
    "level_rewards": {"guild_id", "level", "role_id"},
    "reaction_roles": {"message_id", "emoji", "role_id"},
    "ng_words": {"guild_id", "word"},
    "auto_replies": {"guild_id", "trigger", "response"},
    "reminders": {"id", "user_id", "channel_id", "message", "end_time"},
    "monthly_rules": {"guild_id", "rule_ch", "target_ch"},
    "conversation_history": {
        "id",
        "guild_id",
        "channel_id",
        "user_id",
        "role",
        "content",
        "created_at",
    },
    "tickets": {
        "id",
        "guild_id",
        "channel_id",
        "user_id",
        "category",
        "status",
        "created_at",
        "closed_at",
    },
    "user_stats": {
        "guild_id",
        "user_id",
        "message_count",
        "ai_chat_count",
        "fortune_count",
        "ticket_count",
        "first_seen",
        "last_seen",
    },
    "user_achievements": {
        "guild_id",
        "user_id",
        "achievement_key",
        "unlocked_at",
    },
    "user_titles": {
        "guild_id",
        "user_id",
        "title_key",
        "equipped",
        "unlocked_at",
    },
    "daily_fortunes": {
        "guild_id",
        "user_id",
        "fortune_date",
        "fortune_key",
        "score",
        "created_at",
    },
    "weekly_xp": {"guild_id", "user_id", "week_key", "xp", "updated_at"},
}

REQUIRED_BASELINE_INDEXES = {
    "idx_conversation_lookup",
    "idx_ticket_user",
    "idx_weekly_xp_ranking",
}


async def _validate_baseline_schema(db: aiosqlite.Connection) -> None:
    for table_name, required_columns in REQUIRED_BASELINE_COLUMNS.items():
        cursor = await db.execute(f'PRAGMA table_info("{table_name}")')
        rows = await cursor.fetchall()
        if not rows:
            raise RuntimeError(
                f"Baseline schema validation failed: missing table {table_name}"
            )

        actual_columns = {str(row[1]) for row in rows}
        missing_columns = required_columns - actual_columns
        if missing_columns:
            raise RuntimeError(
                "Baseline schema validation failed: "
                f"table {table_name} is missing columns "
                f"{sorted(missing_columns)}"
            )

    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    actual_indexes = {str(row[0]) for row in await cursor.fetchall()}
    missing_indexes = REQUIRED_BASELINE_INDEXES - actual_indexes
    if missing_indexes:
        raise RuntimeError(
            "Baseline schema validation failed: missing indexes "
            f"{sorted(missing_indexes)}"
        )


async def _baseline_v34_schema(db: aiosqlite.Connection) -> None:
    """Adopt the already-deployed v34 schema without rewriting user data.

    DatabaseManager.init() remains responsible for creating the current baseline
    tables in Phase 3. The baseline is recorded only after the existing schema
    has been validated. Future schema changes are added as numbered migrations.
    """

    await _validate_baseline_schema(db)


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
