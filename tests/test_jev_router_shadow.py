import pytest

from ai_manager import AiManager
from config import Config
from services.jev_model_router import (
    JevModelRouter,
    JevRouteDecision,
    jev_router_mode,
)


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


def test_jev_choice_response_is_parsed_and_confidence_gated():
    router = make_router(threshold=0.85)
    decision = router._parse_response(
        {
            "answers": {
                "model_route": {
                    "type": "choice",
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


def test_jev_low_confidence_is_not_accepted():
    router = make_router(threshold=0.85)
    decision = router._parse_response(
        {
            "answers": {
                "model_route": {
                    "choice": "normal-chat",
                    "probabilities": {
                        "normal-chat": 0.51,
                        "reasoning": 0.47,
                        "deep-reasoning": 0.02,
                    },
                    "confidence": 0.51,
                }
            }
        },
        latency_ms=80,
    )

    assert decision.route == "normal-chat"
    assert decision.accepted is False


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


def test_router_mode_defaults_to_legacy(monkeypatch):
    monkeypatch.delenv("JEV_ROUTER_MODE", raising=False)
    assert jev_router_mode() == "legacy"


def test_invalid_router_mode_fails_closed_to_legacy(monkeypatch):
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
async def test_legacy_mode_skips_jev_and_keeps_legacy_route():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        mode = "legacy"
        is_configured = True

        async def route(self, content):
            raise AssertionError("Jev must not be called in legacy mode")

    manager.jev_router = FakeRouter()

    result = await manager._select_production_route(
        "比較して",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert result == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )


@pytest.mark.asyncio
async def test_shadow_mode_keeps_legacy_route_and_schedules_shadow():
    manager = AiManager.__new__(AiManager)
    scheduled = {}

    class FakeRouter:
        mode = "shadow"
        is_configured = True

    manager.jev_router = FakeRouter()

    def fake_schedule(content, legacy_route):
        scheduled["content"] = content
        scheduled["legacy_route"] = legacy_route

    manager._schedule_jev_shadow = fake_schedule

    result = await manager._select_production_route(
        "短い分析質問",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert result == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )
    assert scheduled == {
        "content": "短い分析質問",
        "legacy_route": "normal-chat",
    }


@pytest.mark.asyncio
async def test_accepted_jev_route_controls_production_model():
    manager = AiManager.__new__(AiManager)

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

    manager.jev_router = FakeRouter()

    model, effort, route = await manager._select_production_route(
        "比較して考えて",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert model == Config.REASONING_MODEL
    assert effort == Config.REASONING_EFFORT
    assert route == "reasoning"


@pytest.mark.asyncio
async def test_deep_jev_route_uses_deep_effort_and_token_budget():
    manager = AiManager.__new__(AiManager)

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

    manager.jev_router = FakeRouter()

    model, effort, route = await manager._select_production_route(
        "体系的に深く分析して",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert model == Config.REASONING_MODEL
    assert effort == Config.DEEP_REASONING_EFFORT
    assert route == "deep-reasoning"
    assert (
        manager.select_chat_max_tokens(route)
        == Config.DEEP_REASONING_MAX_TOKENS
    )


@pytest.mark.asyncio
async def test_low_confidence_jev_falls_back_to_legacy():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.70,
                probabilities={"normal-chat": 0.30, "reasoning": 0.70},
                latency_ms=90,
                accepted=False,
                error=None,
            )

    manager.jev_router = FakeRouter()

    result = await manager._select_production_route(
        "ambiguous",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert result == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )


@pytest.mark.asyncio
async def test_jev_timeout_error_falls_back_to_legacy():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route=None,
                confidence=0.0,
                probabilities={},
                latency_ms=1500,
                accepted=False,
                error="ReadTimeout",
            )

    manager.jev_router = FakeRouter()

    result = await manager._select_production_route(
        "hello",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert result == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )


@pytest.mark.asyncio
async def test_missing_key_in_production_falls_back_without_calling_jev():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        mode = "production"
        is_configured = False

        async def route(self, content):
            raise AssertionError("route must not be called without API key")

    manager.jev_router = FakeRouter()

    result = await manager._select_production_route(
        "hello",
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )

    assert result == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )


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


@pytest.mark.asyncio
async def test_chat_uses_accepted_jev_reasoning_route():
    manager = AiManager.__new__(AiManager)
    captured = {}

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.92,
                probabilities={"normal-chat": 0.08, "reasoning": 0.92},
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
        content="短いけれど分析が必要な質問",
        history=None,
    )

    assert reply == "ok"
    assert model == Config.REASONING_MODEL
    assert route == "reasoning"
    assert captured["model"] == Config.REASONING_MODEL
    assert captured["max_tokens"] == Config.REASONING_MAX_TOKENS
