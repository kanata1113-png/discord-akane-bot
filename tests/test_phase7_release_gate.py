import importlib

import pytest

import app
from config import Config
from database import DatabaseManager
from db_facade import DatabaseFacade
from db_migrations import LATEST_SCHEMA_VERSION, get_schema_version, run_migrations
from repositories import RepositoryRegistry
from runtime_preflight import validate_runtime_environment
from services import ServiceRegistry


EXPECTED_EXTENSIONS = (
    "cogs.admin",
    "cogs.general",
    "cogs.events",
    "cogs.background",
)


def _clear_railway_environment(monkeypatch):
    for key in (
        "RAILWAY_DEPLOYMENT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_VOLUME_MOUNT_PATH",
    ):
        monkeypatch.delenv(key, raising=False)


def test_all_release_extensions_import_and_match_startup_manifest():
    assert app.EXTENSIONS == EXPECTED_EXTENSIONS
    for extension in EXPECTED_EXTENSIONS:
        importlib.import_module(extension)


def test_local_runtime_keeps_existing_database_fallback(monkeypatch):
    _clear_railway_environment(monkeypatch)
    validate_runtime_environment()


def test_railway_runtime_requires_data_volume(monkeypatch):
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "deployment")
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)

    with pytest.raises(RuntimeError, match="persistent volume"):
        validate_runtime_environment()


def test_railway_runtime_requires_expected_mount_path(monkeypatch):
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "deployment")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/wrong")

    with pytest.raises(RuntimeError, match="unexpected path"):
        validate_runtime_environment()


def test_railway_runtime_accepts_expected_persistent_database(monkeypatch):
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "deployment")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/data")
    monkeypatch.setattr("runtime_preflight.os.path.isdir", lambda path: path == "/data")
    monkeypatch.setattr(Config, "DB_NAME", "/data/akane_v26.db")

    validate_runtime_environment()


@pytest.mark.asyncio
async def test_full_db_stack_survives_init_migration_and_facade_roundtrip(tmp_path):
    db_path = str(tmp_path / "release-gate.db")

    legacy = DatabaseManager(db_path)
    await legacy.init()

    applied = await run_migrations(db_path)
    assert [migration.version for migration in applied] == [LATEST_SCHEMA_VERSION]
    assert await get_schema_version(db_path) == LATEST_SCHEMA_VERSION

    repositories = RepositoryRegistry(db_path)
    services = ServiceRegistry(repositories, legacy)
    facade = DatabaseFacade(legacy=legacy, services=services)

    leveled_up, level, xp = await facade.add_xp(123, 150)
    assert (leveled_up, level, xp) == (True, 2, 50)

    await facade.add_conversation_message(1, 2, 123, "user", "release gate")
    history = await facade.get_conversation_history(1, 2, 123)
    assert history == [{"role": "user", "content": "release gate"}]

    applied_again = await run_migrations(db_path)
    assert applied_again == []
    assert await get_schema_version(db_path) == LATEST_SCHEMA_VERSION
