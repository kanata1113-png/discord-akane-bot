import pytest

from config import Config
from services.ai_orchestrator import AIOrchestrator
from services.jev_model_router import JevRouteDecision
from services.routing_policy import RoutingPolicy


@pytest.mark.asyncio
async def test_orchestrator_coordinates_route_prompt_and_execution():
    captured = {}

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.99,
                probabilities={"reasoning": 0.99},
                latency_ms=70,
                accepted=True,
                error=None,
            )

    async def generate(**kwargs):
        captured.update(kwargs)
        return "ok"

    orchestrator = AIOrchestrator(RoutingPolicy(FakeRouter()), generate)
    reply, model, route = await orchestrator.chat(
        user_name="tester",
        content="メリットとデメリットを比較して",
        history=[{"role": "user", "content": "previous"}],
    )

    assert reply == "ok"
    assert model == Config.REASONING_MODEL
    assert route == "reasoning"
    assert captured["model"] == Config.REASONING_MODEL
    assert captured["history"] == [{"role": "user", "content": "previous"}]


@pytest.mark.asyncio
async def test_orchestrator_preserves_regulation_prompt_independent_of_route():
    captured = {}

    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="normal-chat",
                confidence=0.99,
                probabilities={"normal-chat": 0.99},
                latency_ms=60,
                accepted=True,
                error=None,
            )

    async def generate(**kwargs):
        captured.update(kwargs)
        return "ok"

    orchestrator = AIOrchestrator(RoutingPolicy(FakeRouter()), generate)
    await orchestrator.chat(
        user_name="tester",
        content="表現の自由について教えて",
    )

    assert "【表現の自由・規制関連】" in captured["system"]
