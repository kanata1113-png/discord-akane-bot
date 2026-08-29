from __future__ import annotations

import os

from config import Config


EXPECTED_RAILWAY_VOLUME_PATH = "/data"
EXPECTED_PRODUCTION_DB = "/data/akane_v26.db"


def is_railway_runtime() -> bool:
    """Return True only for a running Railway deployment environment."""
    return bool(
        os.getenv("RAILWAY_DEPLOYMENT_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("RAILWAY_PROJECT_ID")
    )


def validate_runtime_environment() -> None:
    """Fail fast when a Railway deployment cannot see the persistent volume.

    Local development keeps the existing relative SQLite fallback. On Railway,
    silently falling back to an ephemeral database would look like data loss, so
    startup is rejected unless the expected /data volume is mounted and the
    configured database path still points at the long-lived v26 database file.
    """
    if not is_railway_runtime():
        return

    mount_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if mount_path != EXPECTED_RAILWAY_VOLUME_PATH:
        raise RuntimeError(
            "Railway persistent volume is missing or mounted at an unexpected "
            f"path: {mount_path!r}. Expected {EXPECTED_RAILWAY_VOLUME_PATH!r}."
        )

    if not os.path.isdir(EXPECTED_RAILWAY_VOLUME_PATH):
        raise RuntimeError(
            "Railway persistent volume path /data is not available at runtime."
        )

    if Config.DB_NAME != EXPECTED_PRODUCTION_DB:
        raise RuntimeError(
            "Railway database path is not the persistent production database: "
            f"{Config.DB_NAME!r}. Expected {EXPECTED_PRODUCTION_DB!r}."
        )
