from cogs.admin import AdminCommands
from cogs.admin_runtime import AdminCommands as RuntimeAdminCommands
from services.admin_capabilities import ADMIN_WRITE_CAPABILITY_SPECS
from services.moderation_capabilities import MODERATION_CAPABILITY_SPECS
from services.message_capability_discovery import DISCOVERY_SPECS


def test_admin_public_entrypoint_uses_stable_runtime():
    assert AdminCommands is RuntimeAdminCommands


def test_privileged_capabilities_are_not_natural_language_discoverable():
    discovery_ids = {spec.capability_id for spec in DISCOVERY_SPECS}
    privileged_ids = {
        *(spec.capability_id for spec in MODERATION_CAPABILITY_SPECS),
        *(spec.capability_id for spec in ADMIN_WRITE_CAPABILITY_SPECS),
    }
    assert privileged_ids.isdisjoint(discovery_ids)


def test_release_h_exact_moderation_scope():
    assert {spec.capability_id for spec in MODERATION_CAPABILITY_SPECS} == {
        "moderation_kick",
        "moderation_ban",
        "moderation_purge",
    }


def test_release_h_preserves_moderation_slash_paths():
    assert {spec.slash_command for spec in MODERATION_CAPABILITY_SPECS} == {
        "/admin kick",
        "/admin ban",
        "/admin purge",
    }


def test_release_h_admin_write_scope_is_exact():
    assert {spec.slash_command for spec in ADMIN_WRITE_CAPABILITY_SPECS} == {
        "/admin config_log",
        "/admin config_welcome",
        "/admin config_starboard",
        "/admin config_autochat",
        "/admin config_monthly",
        "/admin setup_ticket",
        "/admin rolepanel",
        "/admin level_reward",
        "/admin level_reward_remove",
        "/admin filter_add",
        "/admin response_add",
    }


def test_release_h_all_privileged_mutations_require_confirmation():
    for spec in (*MODERATION_CAPABILITY_SPECS, *ADMIN_WRITE_CAPABILITY_SPECS):
        assert spec.requires_confirmation is True
        assert spec.discoverable is False
