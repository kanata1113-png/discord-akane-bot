from services.discovery_policy_audit import (
    LEGACY_BOOKKEEPING_DIRECT_EXECUTION,
    audit_discovery_policy,
    validate_discovery_policy,
)


def test_release_c_discovery_policy_is_internally_consistent():
    validate_discovery_policy()


def test_bookkeeping_exceptions_are_explicit_not_implicit():
    assert LEGACY_BOOKKEEPING_DIRECT_EXECUTION == frozenset(
        {"profile", "achievements"}
    )
    records = {
        record.capability_id: record
        for record in audit_discovery_policy()
    }
    assert records["profile"].reason == "legacy_b2_bookkeeping_exception"
    assert records["achievements"].reason == "legacy_b2_bookkeeping_exception"


def test_argumentful_costly_and_persistent_candidates_remain_selection_only():
    records = {
        record.capability_id: record
        for record in audit_discovery_policy()
    }
    for capability_id in (
        "rankings",
        "fortune",
        "titles",
        "translate",
        "define",
        "summary",
    ):
        assert records[capability_id].direct_executable is False

    for capability_id in ("translate", "define", "summary"):
        assert records[capability_id].incurs_external_cost is True
