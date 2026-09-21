import pytest

from config import Config
from services.ai_orchestrator import AIOrchestrator
from services.budget_controller import BudgetController
from services.intent_controller import IntentController
from services.jev_model_router import JevRouteDecision
from services.orchestration_context import OrchestrationContextBuilder
from services.routing_policy import RoutingPolicy


def test_external_context_excludes_message_bodies():
    secret = "PRIVATE-HISTORY-BODY"
    context = OrchestrationContextBuilder.build(
        "それを詳しく",
        [{"role": "user", "content": secret}],
        previous_route="reasoning",
        previous_intent="analysis",
    )
    hint = context.external.as_hint()
    assert secret not in hint
    assert context.external.followup_like is True
    assert "previous_route:reasoning" in hint
    assert "current_intent:casual-chat" in hint


def test_intent_controller_is_safe_by_default():
    context = OrchestrationContextBuilder.build("英語に翻訳して", [])
    decision = IntentController(enabled=False).decide(context)
    assert decision.requested_pipeline == "translation"
    assert decision.effective_pipeline == "general-chat"
    assert decision.reason == "controller_disabled"


def test_intent_controller_does_not_dispatch_unregistered_pipeline():
    context = OrchestrationContextBuilder.build("英語に翻訳して", [])
    decision = IntentController(enabled=True).decide(
        context,
        supported_pipelines={"general-chat"},
    )
    assert decision.requested_pipeline == "translation"
    assert decision.effective_pipeline == "general-chat"
    assert decision.reason == "pipeline_not_registered"


def test_budget_controller_disabled_preserves_hard_cap():
    context = OrchestrationContextBuilder.build("短く説明して", [])
    decision = BudgetController(enabled=False).decide("reasoning", context)
    assert decision.max_output_tokens == Config.REASONING_MAX_TOKENS
    assert decision.controller_enabled is False


def test_budget_controller_honors_detail_and_hard_cap():
    context = OrchestrationContextBuilder.build("詳しく分析して", [])
    decision = BudgetController(enabled=True).decide("reasoning", context)
    assert decision.max_output_tokens == Config.REASONING_MAX_TOKENS
    assert decision.max_output_tokens <= decision.hard_cap
    assert decision.reason == "requested_detail_cap"


@pytest.mark.asyncio
async def test_orchestrator_build_plan_preserves_existing_route_budget_when_v2_disabled():
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.99,
                probabilities={"reasoning": 0.99},
                latency_ms=10,
                accepted=True,
                error=None,
            )

    async def generate(**kwargs):
        return "ok"

    orchestrator = AIOrchestrator(
        RoutingPolicy(FakeRouter()),
        generate,
        intent_controller=IntentController(enabled=False),
        budget_controller=BudgetController(enabled=False),
    )
    plan = await orchestrator.build_plan(
        user_name="tester",
        content="メリットとデメリットを比較して",
        history=[],
    )

    assert plan.route.route == "reasoning"
    assert plan.budget.max_output_tokens == plan.route.max_output_tokens
    assert plan.intent.effective_pipeline == "general-chat"
