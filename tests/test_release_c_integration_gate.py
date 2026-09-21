from cogs.general import GeneralCog
from cogs.general_commands import GeneralCog as LegacyGeneralCog
from services.ai_capabilities import DEFINE_SPEC, SUMMARY_SPEC, TRANSLATE_SPEC
from services.capability_catalog import (
    DISCOVERY_RELEASE_C_SPECS,
    MIGRATED_GENERAL_CAPABILITY_SPECS,
)
from services.capability_core import CapabilityRisk
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.discovery_policy_audit import validate_discovery_policy
from services.user_capabilities import (
    MEMORY_FORGET_SPEC,
    REMIND_SPEC,
    TITLE_SET_SPEC,
)


def _ids(specs):
    return {spec.capability_id for spec in specs}


def test_release_c_command_surface_is_unchanged():
    legacy = {command.name for command in LegacyGeneralCog.__cog_app_commands__}
    release_c = {command.name for command in GeneralCog.__cog_app_commands__}
    assert release_c == legacy


def test_release_c_catalog_is_unique_and_discovery_is_subset():
    migrated_ids = [
        spec.capability_id
        for spec in MIGRATED_GENERAL_CAPABILITY_SPECS
    ]
    assert len(migrated_ids) == len(set(migrated_ids))
    assert _ids(DISCOVERY_RELEASE_C_SPECS).issubset(set(migrated_ids))


def test_write_confirm_capabilities_never_enter_release_c_discovery():
    discovery_ids = _ids(DISCOVERY_RELEASE_C_SPECS)
    for spec in (TITLE_SET_SPEC, MEMORY_FORGET_SPEC, REMIND_SPEC):
        assert spec.risk is CapabilityRisk.WRITE_CONFIRM
        assert spec.requires_confirmation is True
        assert spec.capability_id not in discovery_ids
        assert spec.capability_id not in DIRECT_EXECUTION_CAPABILITY_IDS


def test_external_cost_ai_capabilities_are_discoverable_but_not_direct_executable():
    discovery_ids = _ids(DISCOVERY_RELEASE_C_SPECS)
    for spec in (TRANSLATE_SPEC, DEFINE_SPEC, SUMMARY_SPEC):
        assert spec.incurs_external_cost is True
        assert spec.capability_id in discovery_ids
        assert spec.capability_id not in DIRECT_EXECUTION_CAPABILITY_IDS


def test_direct_execution_is_subset_of_discovery_and_policy_audit_passes():
    assert DIRECT_EXECUTION_CAPABILITY_IDS.issubset(
        _ids(DISCOVERY_RELEASE_C_SPECS)
    )
    validate_discovery_policy()


def test_release_c_exact_direct_execution_boundary():
    assert DIRECT_EXECUTION_CAPABILITY_IDS == frozenset(
        {
            "level",
            "leaderboard",
            "weekly",
            "profile",
            "achievements",
            "memory_status",
        }
    )
