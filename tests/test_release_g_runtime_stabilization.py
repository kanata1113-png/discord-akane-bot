from cogs.general import GeneralCog as PublicGeneralCog
from cogs.general_runtime import GeneralCog as RuntimeGeneralCog
from services.capability_catalog import (
    DISCOVERY_RELEASE_E_SPECS,
    DISCOVERY_SPECS,
    GENERAL_CAPABILITY_SPECS,
    MIGRATED_GENERAL_CAPABILITY_SPECS,
)
from services.discovery_policy_audit import validate_discovery_policy


def test_public_general_cog_resolves_to_stable_runtime():
    assert PublicGeneralCog is RuntimeGeneralCog


def test_general_catalog_is_complete_and_unique():
    ids = [spec.capability_id for spec in GENERAL_CAPABILITY_SPECS]
    assert len(ids) == 18
    assert len(set(ids)) == 18


def test_discovery_catalog_is_canonical_general_surface():
    assert DISCOVERY_SPECS is GENERAL_CAPABILITY_SPECS


def test_historical_catalog_aliases_preserve_release_f_behavior():
    assert MIGRATED_GENERAL_CAPABILITY_SPECS is GENERAL_CAPABILITY_SPECS
    assert DISCOVERY_RELEASE_E_SPECS is DISCOVERY_SPECS


def test_stable_discovery_policy_passes():
    validate_discovery_policy()
