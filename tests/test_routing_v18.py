import asyncio

import pytest

from config import Config
from services.context_builder import ContextBuilder
from services.jev_model_router import JevRouteDecision
from services.routing_metrics import RoutingTelemetry
from services.routing_policy import RoutingPolicy


class CapturingTelemetry(RoutingTelemetry):
    def __init__(self):
        self.metrics = []

    def emit(self, metric):
        self.metrics.append(metric)


class FakeRouter:
    mode = "production"
    is_configured = True

    def __init__(self):
        self.seen = None

    async def route(self, content):
        self.seen = content
        return JevRouteDecision(
            route="reasoning",
            confidence=0.95,
            probabilities={"reasoning": 0.95},
            latency_ms=100,
            accepted=True,
            error=None,
        )


class LowConfidenceNormalRouter(FakeRouter):
    async def route(self, content):
        self.seen = content
        return JevRouteDecision(
            route="normal-chat",
            confidence=0.45,
            probabilities={"normal-chat": 0.45},
            latency_ms=100,
            accepted=False,
            error=None,
        )


class AcceptedNormalRouter(FakeRouter):
    async def route(self, content):
        self.seen = content
        return JevRouteDecision(
            route="normal-chat",
            confidence=0.96,
            probabilities={"normal-chat": 0.96},
            latency_ms=100,
            accepted=True,
            error=None,
        )


class TimeoutRouter(FakeRouter):
    async def route(self, content):
        self.seen = content
        return JevRouteDecision(
            route=None,
            confidence=None,
            probabilities={},
            latency_ms=1500,
            accepted=False,
            error="timeout",
        )


def analytical_history():
    return [
        {
            "role": "user",
            "content": "SNSの実名制のメリットとデメリットを比較して",
        },
        {"role": "assistant", "content": "answer"},
    ]


def test_context_builder_never_returns_prior_message_content():
    history = [
        {"role": "user", "content": "SECRET PRIOR USER TEXT"},
        {"role": "assistant", "content": "SECRET PRIOR ASSISTANT TEXT"},
    ]
    context = ContextBuilder.build(
        "それをもう少し詳しく",
        history,
        previous_route="reasoning",
        previous_intent="analysis",
    )
    hint = context.as_hint()

    assert context.history_messages == 2
    assert context.followup_like is True
    assert context.previous_route == "reasoning"
    assert context.previous_intent == "analysis"
    assert "previous_route:reasoning" in hint
    assert "previous_intent:analysis" in hint
    assert "SECRET" not in hint
    assert "PRIOR" not in hint


def test_standalone_compare_is_not_misclassified_as_followup():
    history = [{"role": "user", "content": "unrelated previous message"}]
    context = ContextBuilder.build("メリットとデメリットを比較して", history)
    assert context.followup_like is False
    assert context.previous_route is None
    assert context.previous_intent is None


def test_chained_followup_uses_nearest_non_followup_anchor():
    history = analytical_history() + [
        {"role": "user", "content": "それをもう少し詳しく"},
        {"role": "assistant", "content": "expanded answer"},
    ]
    route, intent = RoutingPolicy._previous_user_metadata(history)
    assert route == "reasoning"
    assert intent == "analysis"


@pytest.mark.asyncio
async def test_context_hints_are_opt_in(monkeypatch):
    monkeypatch.delenv("JEV_ROUTER_CONTEXT_HINTS", raising=False)
    router = FakeRouter()
    policy = RoutingPolicy(router)
    await policy.select(
        "それを詳しく",
        history=[{"role": "user", "content": "hidden"}],
    )
    assert router.seen == "それを詳しく"


@pytest.mark.asyncio
async def test_context_hint_contains_continuity_metadata_not_history(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    router = FakeRouter()
    policy = RoutingPolicy(router)
    await policy.select(
        "それをもう少し詳しく",
        history=[
            {
                "role": "user",
                "content": "SNSの実名制のメリットとデメリットを比較して",
            },
            {"role": "assistant", "content": "DO NOT SEND THIS"},
        ],
    )

    assert "routing_context=" in router.seen
    assert "followup:true" in router.seen
    assert "previous_route:reasoning" in router.seen
    assert "previous_intent:analysis" in router.seen
    assert "SNSの実名制" not in router.seen
    assert "DO NOT SEND THIS" not in router.seen


@pytest.mark.asyncio
async def test_non_followup_omits_previous_route_and_intent(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    router = FakeRouter()
    policy = RoutingPolicy(router)
    selection = await policy.select(
        "今日は何してた？",
        history=analytical_history(),
    )

    assert selection.followup_like is False
    assert selection.previous_route is None
    assert selection.previous_intent is None
    assert "previous_route:" not in router.seen
    assert "previous_intent:" not in router.seen


@pytest.mark.asyncio
async def test_low_confidence_followup_uses_reasoning_continuity_floor(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    telemetry = CapturingTelemetry()
    policy = RoutingPolicy(LowConfidenceNormalRouter(), telemetry=telemetry)

    selection = await policy.select(
        "それをもう少し詳しく",
        history=analytical_history(),
    )

    assert selection.route == "reasoning"
    assert selection.model == Config.CHAT_MODEL
    assert selection.source == "legacy"
    assert selection.previous_route == "reasoning"
    assert selection.fallback_reason == "low_confidence_continuity_floor"
    assert telemetry.metrics[0].selected_route == "reasoning"


@pytest.mark.asyncio
async def test_continuity_floor_does_not_override_high_confidence_jev(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    policy = RoutingPolicy(AcceptedNormalRouter())

    selection = await policy.select(
        "それをもう少し詳しく",
        history=analytical_history(),
    )

    assert selection.route == "normal-chat"
    assert selection.model == Config.FAST_MODEL
    assert selection.source == "jev"
    assert selection.fallback_reason is None


@pytest.mark.asyncio
async def test_continuity_floor_does_not_mask_router_errors(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    policy = RoutingPolicy(TimeoutRouter())

    selection = await policy.select(
        "それをもう少し詳しく",
        history=analytical_history(),
    )

    assert selection.route == "normal-chat"
    assert selection.model == Config.FAST_MODEL
    assert selection.source == "legacy"
    assert selection.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_adaptive_budget_is_opt_in_and_bounded(monkeypatch):
    monkeypatch.delenv("AI_ADAPTIVE_TOKEN_BUDGET", raising=False)
    policy = RoutingPolicy(FakeRouter())
    selection = await policy.select("比較して")
    assert selection.max_output_tokens == Config.REASONING_MAX_TOKENS
    assert selection.budget_reason is None

    monkeypatch.setenv("AI_ADAPTIVE_TOKEN_BUDGET", "true")
    policy = RoutingPolicy(FakeRouter())
    selection = await policy.select("比較して")
    assert selection.max_output_tokens <= Config.REASONING_MAX_TOKENS
    assert selection.max_output_tokens == 1600
    assert selection.budget_reason == "short_reasoning"


@pytest.mark.asyncio
async def test_metric_has_ephemeral_event_id_without_identity(monkeypatch):
    monkeypatch.delenv("JEV_ROUTER_CONTEXT_HINTS", raising=False)
    telemetry = CapturingTelemetry()
    policy = RoutingPolicy(FakeRouter(), telemetry=telemetry)
    selection = await policy.select("比較して")

    payload = telemetry.metrics[0].to_dict()
    assert selection.event_id
    assert payload["event_id"] == selection.event_id
    assert "user_id" not in payload
    assert "guild_id" not in payload
    assert "channel_id" not in payload
    assert "content" not in payload
