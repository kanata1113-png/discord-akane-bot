from services.capability_core import CapabilityRisk, CapabilitySpec


def test_external_cost_is_independent_from_execution_risk():
    spec = CapabilitySpec(
        capability_id="translate",
        name="AI翻訳",
        description="AIで翻訳する",
        risk=CapabilityRisk.READ_ONLY,
        category="ai",
        slash_command="/translate",
        incurs_external_cost=True,
    )

    assert spec.risk is CapabilityRisk.READ_ONLY
    assert spec.requires_confirmation is False
    assert spec.incurs_external_cost is True


def test_non_ai_capability_defaults_to_no_external_cost():
    spec = CapabilitySpec(
        capability_id="level",
        name="レベル",
        description="レベル確認",
        risk=CapabilityRisk.READ_ONLY,
        category="progression",
    )

    assert spec.incurs_external_cost is False
