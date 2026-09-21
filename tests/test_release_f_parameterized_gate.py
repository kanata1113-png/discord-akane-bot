from services.discovery_policy_audit import SELECTION_ONLY_REASONS, validate_discovery_policy
from views.capability_candidate_view import (
    PARAMETERIZED_DISCOVERY_IDS,
    RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS,
)


def test_release_f_all_selection_only_capabilities_have_an_interactive_flow():
    assert set(SELECTION_ONLY_REASONS) == (
        set(PARAMETERIZED_DISCOVERY_IDS) | set(RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS)
    )


def test_release_f_parameterized_and_write_flows_are_disjoint():
    assert PARAMETERIZED_DISCOVERY_IDS.isdisjoint(RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS)


def test_release_f_ai_cost_capabilities_stay_selection_only():
    assert {"translate", "define", "summary"} <= PARAMETERIZED_DISCOVERY_IDS


def test_release_f_special_read_side_effects_require_explicit_entry():
    assert {"fortune", "titles"} <= PARAMETERIZED_DISCOVERY_IDS


def test_release_f_discovery_policy_audit_passes():
    validate_discovery_policy()
