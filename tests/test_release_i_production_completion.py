from cogs.admin import AdminCommands as PublicAdminCommands
from cogs.admin_runtime import AdminCommands as RuntimeAdminCommands
from cogs.general import GeneralCog as PublicGeneralCog
from cogs.general_runtime import GeneralCog as RuntimeGeneralCog
from services.admin_capabilities import ADMIN_WRITE_CAPABILITY_SPECS
from services.capability_catalog import GENERAL_CAPABILITY_SPECS
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.moderation_capabilities import MODERATION_CAPABILITY_SPECS
from services.production_baseline import (
    ADMIN_READ_ONLY_SLASH_PATHS,
    EXPECTED_ADMIN_SUBCOMMANDS,
    EXPECTED_GENERAL_CAPABILITIES,
    EXPECTED_PRIVILEGED_MUTATIONS,
    V4_RELEASE,
    validate_v4_production_baseline,
)


def test_release_i_stable_public_runtimes():
    assert PublicGeneralCog is RuntimeGeneralCog
    assert PublicAdminCommands is RuntimeAdminCommands


def test_release_i_machine_readable_baseline_passes():
    baseline = validate_v4_production_baseline()
    assert baseline.release == "v4.0.0"
    assert baseline.slash_addressable_capability_count == 35


def test_release_i_inventory_is_exact():
    assert V4_RELEASE == "v4.0.0"
    assert len(GENERAL_CAPABILITY_SPECS) == EXPECTED_GENERAL_CAPABILITIES == 18
    assert (
        len(ADMIN_WRITE_CAPABILITY_SPECS) + len(MODERATION_CAPABILITY_SPECS)
        == EXPECTED_PRIVILEGED_MUTATIONS
        == 14
    )
    assert (
        len(ADMIN_READ_ONLY_SLASH_PATHS) + EXPECTED_PRIVILEGED_MUTATIONS
        == EXPECTED_ADMIN_SUBCOMMANDS
        == 17
    )


def test_release_i_direct_execution_surface_remains_narrow():
    assert DIRECT_EXECUTION_CAPABILITY_IDS == {
        "level",
        "leaderboard",
        "weekly",
        "profile",
        "achievements",
        "memory_status",
    }


def test_release_i_privileged_surface_is_hidden_and_confirmed():
    for spec in (*ADMIN_WRITE_CAPABILITY_SPECS, *MODERATION_CAPABILITY_SPECS):
        assert spec.discoverable is False
        assert spec.requires_confirmation is True


def test_release_i_read_only_admin_diagnostics_remain_slash_only():
    assert ADMIN_READ_ONLY_SLASH_PATHS == {
        "/admin status",
        "/admin ai_usagedashboard",
        "/admin level_reward_list",
    }
