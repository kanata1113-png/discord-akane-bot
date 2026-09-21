from services.capability_catalog import (
    DISCOVERY_RELEASE_D_SPECS,
    DISCOVERY_RELEASE_E_SPECS,
    MIGRATED_GENERAL_CAPABILITY_SPECS,
)
from services.capability_core import CapabilityRisk
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.discovery_policy_audit import validate_discovery_policy
from services.write_intent_discovery import discover_write_intent
from views.capability_candidate_view import (
    COMMUNITY_WRITE_DISCOVERY_IDS,
    RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS,
    WRITE_CONFIRM_DISCOVERY_IDS,
)


def test_all_18_general_slash_capabilities_are_modeled_in_runtime_catalog():
    ids = {spec.capability_id for spec in MIGRATED_GENERAL_CAPABILITY_SPECS}
    assert len(ids) == 18
    assert {"message_search", "event_create", "poll_create"}.issubset(ids)


def test_release_d_surface_is_frozen_while_release_e_extends_it():
    d_ids = {spec.capability_id for spec in DISCOVERY_RELEASE_D_SPECS}
    e_ids = {spec.capability_id for spec in DISCOVERY_RELEASE_E_SPECS}
    assert e_ids - d_ids == {"message_search", "event_create", "poll_create"}
    assert WRITE_CONFIRM_DISCOVERY_IDS == frozenset(
        {"title_set", "memory_forget", "remind"}
    )
    assert COMMUNITY_WRITE_DISCOVERY_IDS == frozenset(
        {"event_create", "poll_create"}
    )
    assert RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS == frozenset(
        {"title_set", "memory_forget", "remind", "event_create", "poll_create"}
    )


def test_release_e_write_capabilities_never_enter_direct_execution():
    assert not RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS.intersection(
        DIRECT_EXECUTION_CAPABILITY_IDS
    )
    specs = {spec.capability_id: spec for spec in DISCOVERY_RELEASE_E_SPECS}
    assert specs["event_create"].risk is CapabilityRisk.WRITE_CONFIRM
    assert specs["poll_create"].risk is CapabilityRisk.WRITE_CONFIRM
    assert specs["message_search"].risk is CapabilityRisk.READ_ONLY
    assert "message_search" not in DIRECT_EXECUTION_CAPABILITY_IDS


def test_release_e_exact_write_intents_are_local_and_fail_closed():
    assert discover_write_intent("イベントを作って").capability_id == "event_create"
    assert discover_write_intent("投票を作って").capability_id == "poll_create"
    assert discover_write_intent("イベントについて教えて").should_route is False
    assert discover_write_intent("投票についてどう思う").should_route is False


def test_release_e_policy_audit_passes():
    validate_discovery_policy()
