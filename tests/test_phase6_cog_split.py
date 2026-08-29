from __future__ import annotations

import pytest

import app
from cogs.background import BackgroundTasksCog
from cogs.event_handlers import EventsCog as LegacyEventHandlersCog
from cogs.events import EventsCog
from database import DatabaseManager
from repositories import RepositoryRegistry
from services import ServiceRegistry


def test_background_extension_is_loaded_separately():
    assert "cogs.events" in app.EXTENSIONS
    assert "cogs.background" in app.EXTENSIONS


def test_event_cog_overrides_legacy_background_lifecycle():
    assert EventsCog.cog_load is not LegacyEventHandlersCog.cog_load
    assert EventsCog.cog_unload is not LegacyEventHandlersCog.cog_unload


def test_background_cog_owns_scheduled_loops():
    assert hasattr(BackgroundTasksCog, "loop_reminders")
    assert hasattr(BackgroundTasksCog, "loop_monthly")
    assert hasattr(BackgroundTasksCog, "loop_memory_cleanup")


@pytest.mark.asyncio
async def test_due_reminders_are_claimed_atomically(tmp_path):
    db_path = str(tmp_path / "phase6.db")
    legacy = DatabaseManager(db_path)
    await legacy.init()

    repositories = RepositoryRegistry(db_path)
    services = ServiceRegistry(repositories, legacy)

    await repositories.store.execute(
        """
        INSERT INTO reminders (user_id, channel_id, message, end_time)
        VALUES (?, ?, ?, ?)
        """,
        (10, 20, "hello", "2000-01-01T00:00:00+09:00"),
    )

    first = await services.maintenance.claim_due_reminders()
    second = await services.maintenance.claim_due_reminders()

    assert len(first) == 1
    assert first[0][1:] == (10, 20, "hello")
    assert second == []
