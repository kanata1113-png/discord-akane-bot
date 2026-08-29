import sqlite3

import pytest

from database import DatabaseManager
from repositories import RepositoryRegistry


@pytest.mark.asyncio
async def test_registry_uses_same_database_path(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()

    repos = RepositoryRegistry(str(db_path))

    assert repos.store.path == manager.path
    assert repos.guilds.store is repos.store
    assert repos.users.store is repos.store
    assert repos.tickets.store is repos.store
    assert repos.memory.store is repos.store
    assert repos.rankings.store is repos.store


@pytest.mark.asyncio
async def test_guild_repository_matches_legacy_config_behavior(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    repos = RepositoryRegistry(str(db_path))

    await repos.guilds.set_config(10, "welcome_ch", 100)
    assert await manager.get_config(10, "welcome_ch") == 100

    await manager.set_config(10, "welcome_ch", 200)
    assert await repos.guilds.get_config(10, "welcome_ch") == 200

    with pytest.raises(ValueError):
        await repos.guilds.set_config(10, "not_allowed", 1)


@pytest.mark.asyncio
async def test_user_repository_preserves_xp_semantics(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    repos = RepositoryRegistry(str(db_path))

    leveled_up, level, xp = await repos.users.add_xp(123, 150)

    assert (leveled_up, level, xp) == (True, 2, 50)
    assert await manager.get_user_data(123) == (2, 50)
    assert await repos.users.get_user_data(123) == (2, 50)


@pytest.mark.asyncio
async def test_ticket_repository_round_trip(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    repos = RepositoryRegistry(str(db_path))

    ticket_id = await repos.tickets.create(1, 20, 30, "other")
    assert ticket_id > 0

    open_ticket = await repos.tickets.get_open_for_user(1, 30)
    assert open_ticket is not None
    assert open_ticket[1] == 20
    assert open_ticket[2] == "other"

    await repos.tickets.close(20)
    ticket = await repos.tickets.get_by_channel(20)
    assert ticket[5] == "closed"
    assert ticket[7] is not None

    await repos.tickets.delete_by_channel(20)
    assert await repos.tickets.get_by_channel(20) is None


@pytest.mark.asyncio
async def test_memory_repository_round_trip(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    repos = RepositoryRegistry(str(db_path))

    await repos.memory.add_message(1, 2, 3, "user", "hello")
    await repos.memory.add_message(1, 2, 3, "assistant", "hi")

    assert await repos.memory.get_history(1, 2, 3, 10) == [
        ("user", "hello"),
        ("assistant", "hi"),
    ]

    await repos.memory.forget_user(1, 3, 2)
    assert await repos.memory.get_history(1, 2, 3, 10) == []


@pytest.mark.asyncio
async def test_store_transaction_rolls_back_on_failure(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    repos = RepositoryRegistry(str(db_path))

    with pytest.raises(RuntimeError, match="rollback"):
        async with repos.store.transaction() as db:
            await db.execute(
                "INSERT INTO users (user_id, xp, level) VALUES (999, 50, 1)"
            )
            raise RuntimeError("rollback")

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT user_id FROM users WHERE user_id=999"
        ).fetchone()

    assert row is None
