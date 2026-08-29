import sqlite3

import pytest

from database import DatabaseManager
from db_facade import DatabaseFacade
from repositories import RepositoryRegistry
from services import ServiceRegistry


async def build_facade(db_path: str) -> DatabaseFacade:
    legacy = DatabaseManager(db_path)
    await legacy.init()
    repos = RepositoryRegistry(db_path)
    services = ServiceRegistry(repositories=repos, legacy_db=legacy)
    return DatabaseFacade(legacy=legacy, services=services)


@pytest.mark.asyncio
async def test_xp_calls_are_routed_through_service_repository_layer(tmp_path):
    facade = await build_facade(str(tmp_path / "akane.db"))

    leveled_up, level, xp = await facade.add_xp(123, 150)
    info = await facade.get_level_info(123)

    assert (leveled_up, level, xp) == (True, 2, 50)
    assert info == {
        "level": 2,
        "xp": 50,
        "required_xp": 200,
        "remaining_xp": 150,
        "percentage": 25.0,
    }


@pytest.mark.asyncio
async def test_memory_facade_preserves_legacy_return_shapes(tmp_path):
    facade = await build_facade(str(tmp_path / "akane.db"))

    await facade.add_conversation_message(1, 2, 3, "user", "hello")
    await facade.add_conversation_message(1, 2, 3, "assistant", "hi")

    history = await facade.get_conversation_history(1, 2, 3, 12)
    count = await facade.count_conversation_history(1, 2, 3)
    deleted = await facade.clear_conversation_history(1, 2, 3)

    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    assert count == 2
    assert deleted == 2
    assert await facade.count_conversation_history(1, 2, 3) == 0


@pytest.mark.asyncio
async def test_ticket_facade_preserves_legacy_shapes_and_duplicate_guard(tmp_path):
    facade = await build_facade(str(tmp_path / "akane.db"))

    await facade.create_ticket(10, 20, 30, "bot")
    open_ticket = await facade.get_open_ticket(10, 30)
    by_channel = await facade.get_ticket_by_channel(20)

    assert open_ticket[1] == 20
    assert by_channel[1:5] == (10, 30, "bot", "open")

    with pytest.raises(ValueError, match="already has an open ticket"):
        await facade.create_ticket(10, 21, 30, "other")

    await facade.close_ticket(20)
    assert await facade.count_open_tickets(10) == 0


@pytest.mark.asyncio
async def test_unmigrated_methods_still_delegate_to_legacy_manager(tmp_path):
    facade = await build_facade(str(tmp_path / "akane.db"))

    await facade.set_config(55, "log_ch", 99)

    assert await facade.get_config(55, "log_ch") == 99
    assert facade.path.endswith("akane.db")


@pytest.mark.asyncio
async def test_repository_and_legacy_storage_remain_the_same_database(tmp_path):
    db_path = str(tmp_path / "akane.db")
    facade = await build_facade(db_path)

    await facade.add_xp(777, 10)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT level, xp FROM users WHERE user_id=?",
            (777,),
        ).fetchone()

    assert row == (1, 10)
