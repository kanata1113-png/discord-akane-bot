import pytest

from ai_manager import AiManager
from config import Config
from services.jev_model_router import (
    JevModelRouter,
    JevRouteDecision,
    jev_router_mode,
)
from services.routing_metrics import RoutingTelemetry
from services.routing_policy import RoutingPolicy


def make_router(
    api_key="test-key",
    threshold=0.85,
    timeout_seconds=1.5,
    mode="production",
):
    return JevModelRouter(
        api_key=api_key,
        endpoint="https://api.typesafe.ai/v1/systemone",
        model="jev-latest",
        confidence_threshold=threshold,
        timeout_seconds=timeout_seconds,
        mode=mode,
    )


class CapturingTelemetry(RoutingTelemetry):
    def __init__(self):
        self.metrics = []

    def emit(self, metric):
        self.metrics.append(metric)


def test_jev_choice_response_is_parsed_and_confidence_gated():
    router = make_router(threshold=0.85)
    decision = router._parse_response(
        {
            "answers": {
                "model_route": {
                    "choice": "reasoning",
                    "probabilities": {
                        "normal-chat": 0.05,
                        "reasoning": 0.92,
                        "deep-reasoning": 0.03,
                    },
                    "confidence": 0.92,
                }
            }
        },
        latency_ms=123,
    )

    assert decision.route == "reasoning"
    assert decision.confidence == pytest.approx(0.92)
    assert decision.accepted is True
    assert decision.latency_ms == 123
    assert decision.error is None


def test_invalid_jev_route_is_rejected():
    router = make_router()
    decision = router._parse_response(
        {
            "answers": {
                "model_route": {
                    "choice": "unknown-tier",
                    "confidence": 0.99,
                }
            }
        },
        latency_ms=50,
    )

    assert decision.route is None
    assert decision.accepted is False
    assert decision.error == "invalid_route"


def test_router_mode_defaults_and_invalid_values_fail_closed(monkeypatch):
    monkeypatch.delenv("JEV_ROUTER_MODE", raising=False)
    assert jev_router_mode() == "legacy"

    monkeypatch.setenv("JEV_ROUTER_MODE", "unexpected")
    assert jev_router_mode() == "legacy"


def test_from_environment_uses_production_timeout_default(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setenv("JEV_ROUTER_MODE", "production")
    monkeypatch.delenv("JEV_ROUTER_TIMEOUT_SECONDS", raising=False)

    router = JevModelRouter.from_environment()

    assert router.mode == "production"
    assert router.timeout_seconds == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_missing_jev_key_fails_closed_without_network():
    router = make_router(api_key="")
    decision = await router.route("hello")

    assert decision.route is None
    assert decision.accepted is False
    assert decision.error == "missing_api_key"


@pytest.mark.asyncio
async def test_legacy_mode_skips_jev_and_emits_privacy_minimal_metric():
    class FakeRouter:
        mode = "legacy"
        is_configured = True

        async def route(self, content):
            raise AssertionError("Jev must not be called in legacy mode")

    telemetry = CapturingTelemetry()
    policy = RoutingPolicy(FakeRouter(), telemetry=telemetry)
    selection = await policy.select("こんにちは")

    assert selection.route == "normal-chat"
    assert selection.source == "legacy"
    assert len(telemetry.metrics) == 1
    payload = telemetry.metrics[0].to_dict()
    assert payload["mode"] == "legacy"
    assert payload["selected_route"] == "normal-chat"
    assert "content" not in payload
    assert "user_id" not in payload


@pytest.mark.asyncio
async def test_shadow_mode_keeps_legacy_authoritative():
    class FakeRouter:
        mode = "shadow"
        is_configured = False

    telemetry = CapturingTelemetry()
    policy = RoutingPolicy(FakeRouter(), telemetry=telemetry)
    selection = await policy.select("短い分析質問")

    assert selection.source == "legacy"
    assert selection.mode == "shadow"


@pytest.mark.asyncio
async def test_accepted_jev_route_controls_production_model_and_budget():
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.91,
                probabilities={"normal-chat": 0.09, "reasoning": 0.91},
                latency_ms=120,
                accepted=True,
                error=None,
            )

    telemetry = CapturingTelemetry()
    selection = await RoutingPolicy(
        FakeRouter(),
        telemetry=telemetry,
    ).select("比較して考えて")

    assert selection.model == Config.REASONING_MODEL
    assert selection.reasoning_effort == Config.REASONING_EFFORT
    assert selection.route == "reasoning"
    assert selection.max_output_tokens == Config.REASONING_MAX_TOKENS
    assert selection.source == "jev"
    assert telemetry.metrics[0].confidence == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_deep_jev_route_uses_deep_budget():
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="deep-reasoning",
                confidence=0.96,
                probabilities={"deep-reasoning": 0.96},
                latency_ms=110,
                accepted=True,
                error=None,
            )

    selection = await RoutingPolicy(FakeRouter()).select(
        "体系的に深く分析して"
    )

    assert selection.model == Config.REASONING_MODEL
    assert selection.reasoning_effort == Config.DEEP_REASONING_EFFORT
    assert selection.max_output_tokens == Config.DEEP_REASONING_MAX_TOKENS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("decision", "expected_reason"),
    [
        (
            JevRouteDecision(
                route="reasoning",
                confidence=0.70,
                probabilities={"reasoning": 0.70},
                latency_ms=90,
                accepted=False,
                error=None,
            ),
            "low_confidence",
        ),
        (
            JevRouteDecision(
                route=None,
                confidence=0.0,
                probabilities={},
                latency_ms=1500,
                accepted=False,
                error="ReadTimeout",
            ),
            "ReadTimeout",
        ),
    ],
)
async def test_production_rejections_fall_back_to_legacy(
    decision,
    expected_reason,
):
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return decision

    selection = await RoutingPolicy(FakeRouter()).select("hello")

    assert selection.source == "legacy"
    assert selection.route == "normal-chat"
    assert selection.fallback_reason == expected_reason


@pytest.mark.asyncio
async def test_missing_key_in_production_falls_back_without_calling_jev():
    class FakeRouter:
        mode = "production"
        is_configured = False

        async def route(self, content):
            raise AssertionError("route must not be called without API key")

    selection = await RoutingPolicy(FakeRouter()).select("hello")

    assert selection.source == "legacy"
    assert selection.fallback_reason == "not_configured"


@pytest.mark.asyncio
async def test_regulation_prompt_is_preserved_when_jev_selects_normal_chat():
    manager = AiManager.__new__(AiManager)
    captured = {}

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="normal-chat",
                confidence=0.99,
                probabilities={"normal-chat": 0.99},
                latency_ms=100,
                accepted=True,
                error=None,
            )

    async def fake_call_gpt(**kwargs):
        captured.update(kwargs)
        return "ok"

    manager.jev_router = FakeRouter()
    manager.call_gpt = fake_call_gpt

    reply, model, route = await manager.chat(
        user_name="tester",
        content="表現の自由について教えて",
        history=None,
    )

    assert reply == "ok"
    assert model == Config.CHAT_MODEL
    assert route == "normal-chat"
    assert "【表現の自由・規制関連】" in captured["system"]


def test_specialized_tasks_remain_outside_jev_routing():
    assert Config.FAST_MODEL != Config.REASONING_MODEL
    system, user = AiManager.get_system_prompt(), "hello"
    assert system
    assert user == "hello"
