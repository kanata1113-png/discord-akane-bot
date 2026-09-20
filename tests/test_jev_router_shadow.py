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
async def test_shadow_disagreement_is_logged_but_does_not_change_legacy_route(caplog):
    caplog.set_level(logging.INFO, logger="AkaneBot")
    manager = AiManager.__new__(AiManager)

    class FakeRouter:
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="normal-chat",
                confidence=0.97,
                probabilities={"normal-chat": 0.97, "reasoning": 0.03},
                latency_ms=100,
                accepted=True,
                error=None,
            )

    manager.jev_router = FakeRouter()

    await manager._run_jev_shadow(
        "憲法上の論点を比較して",
        "regulation",
    )

    assert "JEV shadow" in caplog.text
    assert "legacy=reasoning" in caplog.text
    assert "jev=normal-chat" in caplog.text
    assert "match=False" in caplog.text


@pytest.mark.asyncio
async def test_chat_keeps_legacy_router_authoritative_in_shadow_v01():
    manager = AiManager.__new__(AiManager)
    scheduled = {}
    captured = {}

    def fake_schedule(content, legacy_route):
        scheduled["content"] = content
        scheduled["legacy_route"] = legacy_route

    async def fake_call_gpt(**kwargs):
        captured.update(kwargs)
        return "ok"

    manager._schedule_jev_shadow = fake_schedule
    manager.call_gpt = fake_call_gpt

    reply, model, route = await manager.chat(
        user_name="tester",
        content="憲法上の表現の自由を分析して",
        history=None,
    )

    assert reply == "ok"
    assert model == Config.REASONING_MODEL
    assert route == "regulation"
    assert scheduled["legacy_route"] == "regulation"
    assert captured["model"] == Config.REASONING_MODEL
    assert captured["max_tokens"] == Config.REASONING_MAX_TOKENS
