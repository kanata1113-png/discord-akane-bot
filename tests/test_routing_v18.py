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


def test_context_builder_never_returns_prior_message_content():
    history = [
        {"role": "user", "content": "SECRET PRIOR USER TEXT"},
        {"role": "assistant", "content": "SECRET PRIOR ASSISTANT TEXT"},
    ]
    context = ContextBuilder.build("それをもう少し詳しく", history)
    hint = context.as_hint()

    assert context.history_messages == 2
    assert context.followup_like is True
    assert "SECRET" not in hint
    assert "PRIOR" not in hint


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
async def test_context_hint_contains_metadata_not_history(monkeypatch):
    monkeypatch.setenv("JEV_ROUTER_CONTEXT_HINTS", "true")
    router = FakeRouter()
    policy = RoutingPolicy(router)
    await policy.select(
        "それを詳しく",
        history=[{"role": "user", "content": "DO NOT SEND THIS"}],
    )

    assert "routing_context=" in router.seen
    assert "followup:true" in router.seen
    assert "DO NOT SEND THIS" not in router.seen


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
