from dataclasses import replace

import pytest

from config import Config
from services.ai_orchestrator import AIOrchestrator
from services.cost_telemetry import CostTelemetry, UsageEvent
from services.detail_intent import DetailIntent
from services.intent_controller import IntentController
from services.output_budget import OutputBudgetPolicy
from services.routing_policy import RoutingPolicy
from services.sol_promotion import SolPromotionGate


def test_detail_intent_levels():
    assert DetailIntent.classify("短く教えて").level == "compact"
    assert DetailIntent.classify("普通に教えて").level == "default"
    assert DetailIntent.classify("できるだけ詳しく教えて").level == "expanded"


def test_output_budget_default_tiers():
    assert OutputBudgetPolicy.for_request(Config.FAST_MODEL, "default", 1500).target_characters == 420
    assert OutputBudgetPolicy.for_request(Config.CHAT_MODEL, "default", 2000).target_characters == 840
    assert OutputBudgetPolicy.for_request(Config.REASONING_MODEL, "default", 3000).target_characters == 1680


def test_expanded_terra_uses_full_reasoning_cap():
    budget = OutputBudgetPolicy.for_request(
        Config.CHAT_MODEL,
        "expanded",
        Config.REASONING_MAX_TOKENS,
    )
    assert budget.target_characters == 1200
    assert budget.max_output_tokens == Config.REASONING_MAX_TOKENS
    assert budget.reason == "output_budget_expanded"


def test_sol_gate_demotes_weak_deep_route():
    selection = RoutingPolicy.legacy_selection("徹底的に")
    selection = replace(selection, model=Config.REASONING_MODEL, route="deep-reasoning")
    gated, decision = SolPromotionGate.apply(selection, "徹底的に説明して")
    assert not decision.promoted
    assert gated.model == Config.CHAT_MODEL


def test_sol_gate_keeps_explicit_complex_deep_route():
    selection = RoutingPolicy.legacy_selection("複数の観点から厳密に比較し、根拠も示して")
    selection = replace(selection, model=Config.REASONING_MODEL, route="deep-reasoning")
    gated, decision = SolPromotionGate.apply(selection, "複数の観点から厳密に比較し、根拠も示して")
    assert decision.promoted
    assert gated.model == Config.REASONING_MODEL


def test_cost_telemetry_summary_is_metadata_only():
    telemetry = CostTelemetry()
    telemetry.record(UsageEvent(Config.FAST_MODEL, "normal-chat", 100, 50, 150, estimated_cost_units=0.075))
    telemetry.record(UsageEvent(Config.REASONING_MODEL, "deep-reasoning", 200, 100, 300, estimated_cost_units=0.9))
    summary = telemetry.summary()
    assert summary["requests"] == 2
    assert summary["sol_rate"] == 50.0
    assert summary["input_tokens"] == 300
    assert summary["output_tokens"] == 150


@pytest.mark.asyncio
async def test_orchestrator_forwards_selected_route_to_generate():
    class FakeRouter:
        mode = "legacy"
        is_configured = False

    captured = {}

    async def generate(**kwargs):
        captured.update(kwargs)
        return "ok"

    orchestrator = AIOrchestrator(
        RoutingPolicy(FakeRouter()),
        generate,
        intent_controller=IntentController(enabled=False),
    )
    plan = await orchestrator.build_plan(
        user_name="tester",
        content="SNSの実名制のメリットとデメリットを比較して",
        history=[],
    )
    await orchestrator.execute(plan, history=[])

    assert captured["route"] == plan.route.route
    assert captured["route"] == "reasoning"
