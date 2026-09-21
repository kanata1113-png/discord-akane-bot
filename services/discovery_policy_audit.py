from __future__ import annotations

from dataclasses import dataclass

from services.capability_catalog import DISCOVERY_RELEASE_E_SPECS
from services.capability_core import CapabilityRisk, CapabilitySpec
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS


@dataclass(frozen=True, slots=True)
class DiscoveryPolicyRecord:
    capability_id: str
    discoverable: bool
    direct_executable: bool
    risk: CapabilityRisk
    incurs_external_cost: bool
    reason: str


SELECTION_ONLY_REASONS = {
    "rankings": "required_argument",
    "fortune": "first_read_persistence",
    "titles": "unlock_bookkeeping",
    "translate": "required_arguments_and_external_cost",
    "define": "required_arguments_and_external_cost",
    "summary": "required_arguments_and_external_cost",
    "title_set": "write_confirm_flow",
    "memory_forget": "write_confirm_flow",
    "remind": "write_confirm_flow",
    "message_search": "required_arguments",
    "event_create": "write_confirm_flow",
    "poll_create": "write_confirm_flow",
}

LEGACY_BOOKKEEPING_DIRECT_EXECUTION = frozenset({"profile", "achievements"})


def audit_discovery_policy(
    specs: tuple[CapabilitySpec, ...] = DISCOVERY_RELEASE_E_SPECS,
) -> tuple[DiscoveryPolicyRecord, ...]:
    records = []
    for spec in specs:
        direct = spec.capability_id in DIRECT_EXECUTION_CAPABILITY_IDS
        if direct:
            reason = (
                "legacy_b2_bookkeeping_exception"
                if spec.capability_id in LEGACY_BOOKKEEPING_DIRECT_EXECUTION
                else "approved_direct_execution"
            )
        else:
            reason = SELECTION_ONLY_REASONS.get(
                spec.capability_id,
                "selection_only",
            )
        records.append(
            DiscoveryPolicyRecord(
                capability_id=spec.capability_id,
                discoverable=spec.discoverable,
                direct_executable=direct,
                risk=spec.risk,
                incurs_external_cost=spec.incurs_external_cost,
                reason=reason,
            )
        )
    return tuple(records)


def validate_discovery_policy() -> None:
    records = audit_discovery_policy()
    ids = {record.capability_id for record in records}

    unknown_direct = DIRECT_EXECUTION_CAPABILITY_IDS - ids
    if unknown_direct:
        raise ValueError(
            f"direct execution capability missing from discovery catalog: {sorted(unknown_direct)}"
        )

    for record in records:
        if record.direct_executable:
            if record.risk is not CapabilityRisk.READ_ONLY:
                raise ValueError(
                    f"non-read capability is direct executable: {record.capability_id}"
                )
            if record.incurs_external_cost:
                raise ValueError(
                    f"external-cost capability is direct executable: {record.capability_id}"
                )
        elif record.capability_id in DIRECT_EXECUTION_CAPABILITY_IDS:
            raise ValueError(
                f"direct execution policy mismatch: {record.capability_id}"
            )

    expected_selection_only = set(SELECTION_ONLY_REASONS)
    actual_selection_only = {
        record.capability_id
        for record in records
        if not record.direct_executable
    }
    if actual_selection_only != expected_selection_only:
        raise ValueError(
            "selection-only discovery set drifted: "
            f"expected={sorted(expected_selection_only)} "
            f"actual={sorted(actual_selection_only)}"
        )

    for record in records:
        if record.risk is CapabilityRisk.WRITE_CONFIRM:
            if record.direct_executable:
                raise ValueError(
                    f"WRITE_CONFIRM bypassed confirmation flow: {record.capability_id}"
                )
            if record.reason != "write_confirm_flow":
                raise ValueError(
                    f"WRITE_CONFIRM missing explicit flow policy: {record.capability_id}"
                )
