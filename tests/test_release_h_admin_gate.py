from cogs.admin import AdminCommands
from cogs.admin_runtime import AdminCommands as RuntimeAdminCommands
from services.moderation_capabilities import MODERATION_CAPABILITY_SPECS
from services.message_capability_discovery import DISCOVERY_SPECS


def test_admin_public_entrypoint_uses_stable_runtime():
    assert AdminCommands is RuntimeAdminCommands


def test_moderation_capabilities_are_not_natural_language_discoverable():
    discovery_ids = {spec.capability_id for spec in DISCOVERY_SPECS}
    moderation_ids = {spec.capability_id for spec in MODERATION_CAPABILITY_SPECS}
    assert moderation_ids.isdisjoint(discovery_ids)


def test_release_h_exact_moderation_scope():
    assert {spec.capability_id for spec in MODERATION_CAPABILITY_SPECS} == {
        "moderation_kick",
        "moderation_ban",
        "moderation_purge",
    }


def test_release_h_preserves_admin_slash_paths():
    assert {spec.slash_command for spec in MODERATION_CAPABILITY_SPECS} == {
        "/admin kick",
        "/admin ban",
        "/admin purge",
    }
