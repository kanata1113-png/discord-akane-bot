from types import SimpleNamespace

import pytest

from ai_manager import AiManager
from cogs.background import BackgroundTasksCog
from cogs.event_handlers import EventsCog
from config import Config


def test_chat_output_limits_are_route_specific():
    assert Config.NORMAL_CHAT_MAX_TOKENS == 1500
    assert Config.REASONING_MAX_TOKENS == 2000
    assert Config.DEEP_REASONING_MAX_TOKENS == 3000

    assert AiManager.select_chat_max_tokens("normal-chat") == 1500
    assert AiManager.select_chat_max_tokens("regulation") == 2000
    assert AiManager.select_chat_max_tokens("reasoning") == 2000
    assert AiManager.select_chat_max_tokens("long-question") == 2000
    assert AiManager.select_chat_max_tokens("deep-reasoning") == 3000


@pytest.mark.asyncio
async def test_chat_passes_reasoning_limit_to_responses_call():
    manager = AiManager.__new__(AiManager)
    captured = {}

    async def fake_call_gpt(**kwargs):
        captured.update(kwargs)
        return "ok"

    manager.call_gpt = fake_call_gpt

    reply, model, route = await manager.chat(
        user_name="tester",
        content="憲法上の表現の自由を分析して",
        history=None,
    )

    assert reply == "ok"
    assert model == Config.REASONING_MODEL
    assert route == "regulation"
    assert captured["max_tokens"] == 2000


@pytest.mark.asyncio
async def test_chat_passes_deep_reasoning_limit_to_responses_call():
    manager = AiManager.__new__(AiManager)
    captured = {}

    async def fake_call_gpt(**kwargs):
        captured.update(kwargs)
        return "ok"

    manager.call_gpt = fake_call_gpt

    reply, model, route = await manager.chat(
        user_name="tester",
        content="表現の自由について多角的に詳細に分析して",
        history=None,
    )

    assert reply == "ok"
    assert model == Config.REASONING_MODEL
    assert route == "deep-reasoning"
    assert captured["max_tokens"] == 3000


@pytest.mark.asyncio
async def test_max_output_tokens_incomplete_response_gets_notice(caplog):
    response = SimpleNamespace(
        output_text="途中までの回答",
        status="incomplete",
        incomplete_details=SimpleNamespace(
            reason="max_output_tokens"
        ),
    )

    class FakeResponses:
        async def create(self, **kwargs):
            return response

    manager = AiManager.__new__(AiManager)
    manager.client = SimpleNamespace(
        responses=FakeResponses()
    )

    result = await manager.call_gpt(
        system="system",
        user="user",
        model=Config.REASONING_MODEL,
        max_tokens=2000,
        reasoning_effort=Config.REASONING_EFFORT,
    )

    assert result.startswith("途中までの回答")
    assert Config.INCOMPLETE_OUTPUT_MSG in result
    assert "AI response incomplete" in caplog.text
    assert "reason=max_output_tokens" in caplog.text


@pytest.mark.asyncio
async def test_completed_response_does_not_get_incomplete_notice():
    response = SimpleNamespace(
        output_text="最後までの回答",
        status="completed",
        incomplete_details=None,
    )

    class FakeResponses:
        async def create(self, **kwargs):
            return response

    manager = AiManager.__new__(AiManager)
    manager.client = SimpleNamespace(
        responses=FakeResponses()
    )

    result = await manager.call_gpt(
        system="system",
        user="user",
        model=Config.CHAT_MODEL,
        max_tokens=1500,
        reasoning_effort=Config.CHAT_REASONING_EFFORT,
    )

    assert result == "最後までの回答"
    assert Config.INCOMPLETE_OUTPUT_MSG not in result


def test_background_tasks_have_single_owner():
    for task_name in (
        "loop_reminders",
        "loop_monthly",
        "loop_memory_cleanup",
    ):
        assert not hasattr(EventsCog, task_name)
        assert hasattr(BackgroundTasksCog, task_name)
