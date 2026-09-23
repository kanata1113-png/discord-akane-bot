import pytest

from config import Config
from services.ai_orchestrator import AIOrchestrator
from services.jev_model_router import JevRouteDecision
from services.prompt_builder import PromptBuilder
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
    assert model == Config.CHAT_MODEL
    assert route == "reasoning"
    assert captured["model"] == Config.CHAT_MODEL
    assert "おおむね840文字以内" in captured["system"]
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
    assert "おおむね420文字以内" in captured["system"]
    assert captured["model"] == Config.FAST_MODEL


def test_cost_routing_model_tiers():
    assert RoutingPolicy.tier_for_route("normal-chat").model == Config.FAST_MODEL
    assert RoutingPolicy.tier_for_route("reasoning").model == Config.CHAT_MODEL
    assert RoutingPolicy.tier_for_route("regulation").model == Config.CHAT_MODEL
    assert RoutingPolicy.tier_for_route("long-question").model == Config.CHAT_MODEL
    assert RoutingPolicy.tier_for_route("deep-reasoning").model == Config.REASONING_MODEL


def test_response_length_targets_follow_model_tiers():
    assert PromptBuilder.response_length_target(
        Config.FAST_MODEL, Config.FAST_REASONING_EFFORT
    ) == 420
    assert PromptBuilder.response_length_target(
        Config.CHAT_MODEL, Config.CHAT_REASONING_EFFORT
    ) == 840
    assert PromptBuilder.response_length_target(
        Config.REASONING_MODEL, Config.DEEP_REASONING_EFFORT
    ) == 1680


def test_response_style_uses_compact_discord_markdown():
    prompt = PromptBuilder.response_style_prompt(Config.REASONING_MODEL)

    assert "おおむね1680文字以内" in prompt
    assert "絵文字" in prompt
    assert "Markdown" in prompt
    assert "# / ## / ### は使わない" in prompt
    assert "**太字**" in prompt
    assert "空行を何行も連続させない" in prompt
    assert "ユーザーが長さ、形式、詳しさを明示した場合" in prompt
