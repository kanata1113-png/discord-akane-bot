from services.capability_catalog import (
    DISCOVERY_PILOT_SPECS,
    MIGRATED_GENERAL_CAPABILITY_SPECS,
)


def test_migrated_catalog_has_unique_capability_ids():
    ids = [spec.capability_id for spec in MIGRATED_GENERAL_CAPABILITY_SPECS]
    assert len(ids) == len(set(ids))


def test_discovery_pilot_surface_is_unchanged():
    assert tuple(spec.capability_id for spec in DISCOVERY_PILOT_SPECS) == (
        "level",
        "weekly",
        "rankings",
        "profile",
        "achievements",
        "fortune",
    )


def test_migrated_catalog_contains_new_release_c_capabilities():
    ids = {spec.capability_id for spec in MIGRATED_GENERAL_CAPABILITY_SPECS}
    assert {
        "leaderboard",
        "titles",
        "title_set",
        "memory_status",
        "memory_forget",
        "remind",
        "translate",
        "define",
        "summary",
    }.issubset(ids)
