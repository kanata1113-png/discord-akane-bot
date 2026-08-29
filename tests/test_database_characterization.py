import sqlite3

import pytest

from config import Config
from database import DatabaseManager


EXPECTED_TABLES = {
    "usage_log",
    "starboard_log",
    "guild_settings",
    "users",
    "level_rewards",
    "reaction_roles",
    "ng_words",
    "auto_replies",
    "reminders",
    "monthly_rules",
    "conversation_history",
    "tickets",
    "user_stats",
    "user_achievements",
    "user_titles",
    "daily_fortunes",
    "weekly_xp",
}

EXPECTED_INDEXES = {
    "idx_conversation_lookup",
    "idx_ticket_user",
    "idx_weekly_xp_ranking",
}


@pytest.mark.asyncio
async def test_empty_database_initializes_current_schema(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))

    await manager.init()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if row[0] != "sqlite_sequence"
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            if not row[0].startswith("sqlite_autoindex_")
        }

    assert tables == EXPECTED_TABLES
    assert EXPECTED_INDEXES <= indexes


@pytest.mark.asyncio
async def test_database_init_is_idempotent(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))

    await manager.init()
    await manager.init()

    with sqlite3.connect(db_path) as connection:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()[0]

    assert table_count == 1


def test_required_xp_formula_is_stable():
    assert DatabaseManager.required_xp(1) == 100
    assert DatabaseManager.required_xp(2) == 200
    assert DatabaseManager.required_xp(5) == 500
    assert DatabaseManager.required_xp(20) == 2000


@pytest.mark.asyncio
async def test_xp_preserves_leftover_after_level_up(tmp_path):
    manager = DatabaseManager(str(tmp_path / "akane.db"))
    await manager.init()

    leveled_up, level, xp = await manager.add_xp(123, 150)

    assert leveled_up is True
    assert level == 2
    assert xp == 50


@pytest.mark.asyncio
async def test_default_xp_award_uses_config_value(tmp_path):
    manager = DatabaseManager(str(tmp_path / "akane.db"))
    await manager.init()

    leveled_up, level, xp = await manager.add_xp(456)

    assert Config.XP_PER_MESSAGE == 10
    assert leveled_up is False
    assert level == 1
    assert xp == 10
