from dataclasses import dataclass

from services.adaptive_routing import (
    AdaptiveRoutingController,
    AdaptiveRoutingProfile,
)


@dataclass(frozen=True)
class Decision:
    route: str | None
    confidence: float
    probabilities: dict[str, float]
    latency_ms: int
    accepted: bool
    error: str | None = None


def test_controller_disabled_preserves_provider_acceptance():
    controller = AdaptiveRoutingController(enabled=False)
    decision = Decision("reasoning", 0.83, {}, 1, False)
    result = controller.evaluate(decision)
    assert result.accepted is False
    assert result.reason == "controller_disabled"


def test_reasoning_threshold_can_be_route_specific_when_enabled():
    controller = AdaptiveRoutingController(enabled=True)
    decision = Decision("reasoning", 0.83, {}, 1, False)
    result = controller.evaluate(decision)
    assert result.threshold == 0.82
    assert result.accepted is True


def test_followup_discount_only_applies_to_analytical_routes():
    profile = AdaptiveRoutingProfile(followup_discount=0.02)
    controller = AdaptiveRoutingController(enabled=True, profile=profile)
    assert controller.threshold_for("reasoning", followup_like=True) == 0.80
    assert controller.threshold_for("normal-chat", followup_like=True) == 0.88


def test_provider_error_never_becomes_accepted():
    controller = AdaptiveRoutingController(enabled=True)
    decision = Decision(None, 1.0, {}, 1, False, "timeout")
    result = controller.evaluate(decision)
    assert result.accepted is False
    assert result.reason == "provider_error"
