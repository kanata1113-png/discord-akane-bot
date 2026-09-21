from services.capability_catalog import DISCOVERY_RELEASE_D_SPECS
from services.capability_core import CapabilityRisk
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.discovery_policy_audit import audit_discovery_policy, validate_discovery_policy
from views.capability_candidate_view import WRITE_CONFIRM_DISCOVERY_IDS


def test_release_d_catalog_has_exact_write_confirm_pilot():
    write_ids = {
        spec.capability_id
        for spec in DISCOVERY_RELEASE_D_SPECS
        if spec.risk is CapabilityRisk.WRITE_CONFIRM
    }
    assert write_ids == {"title_set", "memory_forget", "remind"}
    assert write_ids == set(WRITE_CONFIRM_DISCOVERY_IDS)


def test_release_d_write_confirm_never_enters_direct_execution():
    assert set(WRITE_CONFIRM_DISCOVERY_IDS).isdisjoint(
        DIRECT_EXECUTION_CAPABILITY_IDS
    )


def test_release_d_policy_audit_passes():
    validate_discovery_policy()
    records = {record.capability_id: record for record in audit_discovery_policy()}
    for capability_id in WRITE_CONFIRM_DISCOVERY_IDS:
        record = records[capability_id]
        assert record.risk is CapabilityRisk.WRITE_CONFIRM
        assert record.direct_executable is False
        assert record.reason == "write_confirm_flow"
