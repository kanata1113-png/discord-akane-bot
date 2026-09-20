import logging
from types import SimpleNamespace

import pytest

from ai_manager import AiManager
from config import Config
from services.jev_model_router import JevModelRouter, JevRouteDecision


def make_router(api_key="test-key", threshold=0.85):
    return JevModelRouter(
        api_key=api_key,
        endpoint="https://api.typesafe.ai/v1/systemone",
        model="jev-latest",
        confidence_threshold=threshold,
        timeout_seconds=3.0,
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


@pytest.mark.asyncio
async def test_missing_jev_key_fails_closed_without_network():
    router = make_router(api_key="")
    decision = await router.route("hello")

    assert decision.route is None
    assert decision.accepted is False
    assert decision.error == "missing_api_key"



@pytest.mark.asyncio
async def test_accepted_jev_route_controls_production_model():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
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
async def test_low_confidence_jev_falls_back_to_legacy():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
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
async def test_jev_error_falls_back_to_legacy():
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route=None,
                confidence=0.0,
                probabilities={},
                latency_ms=3000,
                accepted=False,
                error="TimeoutException",
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
async def test_regulation_prompt_is_preserved_when_jev_selects_normal_chat():
    manager = AiManager.__new__(AiManager)
    captured = {}

    class FakeRouter:
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

