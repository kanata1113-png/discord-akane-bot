from __future__ import annotations

from dataclasses import dataclass

from services.admin_capabilities import ADMIN_WRITE_CAPABILITY_SPECS
from services.capability_catalog import GENERAL_CAPABILITY_SPECS
from services.capability_core import CapabilityRisk
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.discovery_policy_audit import validate_discovery_policy
from services.moderation_capabilities import MODERATION_CAPABILITY_SPECS


V4_RELEASE = "v4.0.0"
EXPECTED_TOP_LEVEL_SLASH_COMMANDS = 19
EXPECTED_GENERAL_CAPABILITIES = 18
EXPECTED_ADMIN_SUBCOMMANDS = 17
EXPECTED_PRIVILEGED_MUTATIONS = 14

# These three operator diagnostics intentionally remain authorized slash-only
# reads. They do not need mutation confirmation and are not NL-discoverable.
ADMIN_READ_ONLY_SLASH_PATHS = frozenset(
    {
        "/admin status",
        "/admin ai_cost",
        "/admin level_reward_list",
    }
)


@dataclass(frozen=True, slots=True)
class ProductionBaseline:
    release: str
    general_capability_count: int
    privileged_mutation_count: int
    admin_read_only_count: int
    direct_execution_count: int

    @property
    def slash_addressable_capability_count(self) -> int:
        return (
            self.general_capability_count
            + self.privileged_mutation_count
            + self.admin_read_only_count
        )


def build_production_baseline() -> ProductionBaseline:
    return ProductionBaseline(
        release=V4_RELEASE,
        general_capability_count=len(GENERAL_CAPABILITY_SPECS),
        privileged_mutation_count=(
            len(ADMIN_WRITE_CAPABILITY_SPECS)
            + len(MODERATION_CAPABILITY_SPECS)
        ),
        admin_read_only_count=len(ADMIN_READ_ONLY_SLASH_PATHS),
        direct_execution_count=len(DIRECT_EXECUTION_CAPABILITY_IDS),
    )


def validate_v4_production_baseline() -> ProductionBaseline:
    baseline = build_production_baseline()

    if baseline.general_capability_count != EXPECTED_GENERAL_CAPABILITIES:
        raise ValueError("general capability count drifted")
    if baseline.privileged_mutation_count != EXPECTED_PRIVILEGED_MUTATIONS:
        raise ValueError("privileged mutation count drifted")
    if baseline.admin_read_only_count + baseline.privileged_mutation_count != EXPECTED_ADMIN_SUBCOMMANDS:
        raise ValueError("admin subcommand inventory drifted")
    if baseline.slash_addressable_capability_count != 35:
        raise ValueError("slash-addressable capability inventory drifted")

    general_ids = [spec.capability_id for spec in GENERAL_CAPABILITY_SPECS]
    privileged_specs = (*ADMIN_WRITE_CAPABILITY_SPECS, *MODERATION_CAPABILITY_SPECS)
    privileged_ids = [spec.capability_id for spec in privileged_specs]

    if len(set(general_ids)) != len(general_ids):
        raise ValueError("duplicate general capability id")
    if len(set(privileged_ids)) != len(privileged_ids):
        raise ValueError("duplicate privileged capability id")
    if set(general_ids) & set(privileged_ids):
        raise ValueError("general and privileged capability ids overlap")

    for spec in privileged_specs:
        if spec.discoverable:
            raise ValueError(f"privileged capability became discoverable: {spec.capability_id}")
        if not spec.requires_confirmation:
            raise ValueError(f"privileged capability lost confirmation: {spec.capability_id}")
        if spec.risk not in {CapabilityRisk.ADMIN, CapabilityRisk.MODERATION}:
            raise ValueError(f"privileged capability risk drifted: {spec.capability_id}")

    validate_discovery_policy()
    return baseline
