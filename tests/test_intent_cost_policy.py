import pytest

from services.cost_policy import CostPolicy
from services.intent_gate import IntentGate
from services.jev_model_router import JevRouteDecision
from services.routing_policy import RoutingPolicy


def test_intent_gate_is_observational_and_deterministic():
    assert IntentGate.classify("これを英語に翻訳して") == "translation-like"
    assert IntentGate.classify("この文章を要約して") == "summary-like"
    assert IntentGate.classify("自由とは何？") == "definition-like"
    assert IntentGate.classify("メリットを比較して") == "analysis"


def test_relative_cost_estimator_is_positive():
    assert CostPolicy.estimate_units("unknown-model", 1000) > 0


@pytest.mark.asyncio
async def test_intent_and_cost_do_not_change_selected_route():
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.99,
                probabilities={"reasoning": 0.99},
                latency_ms=80,
                accepted=True,
                error=None,
            )

    selection = await RoutingPolicy(FakeRouter()).select("メリットを比較して")
    assert selection.route == "reasoning"
    assert selection.intent_hint == "analysis"
    assert selection.estimated_cost_units is not None
