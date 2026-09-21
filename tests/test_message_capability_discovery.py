import pytest

from services.jev_discovery_reranker import DiscoveryRerankResult
from services.message_capability_discovery import discover_message_capabilities


class RecordingReranker:
    def __init__(self):
        self.calls = []

    async def rerank(self, content, candidates):
        self.calls.append((content, tuple(candidates)))
        return DiscoveryRerankResult(
            tuple(candidates),
            False,
            0.0,
            0,
            "local_fallback",
        )


@pytest.mark.asyncio
async def test_ordinary_chat_never_reaches_reranker():
    reranker = RecordingReranker()

    result = await discover_message_capabilities(
        "今日はいい天気だね",
        reranker=reranker,
    )

    assert result.should_show_panel is False
    assert result.source == "gate_rejected"
    assert reranker.calls == []


@pytest.mark.asyncio
async def test_action_request_composes_local_and_rerank_layers():
    reranker = RecordingReranker()

    result = await discover_message_capabilities(
        "今週のXPランキングを見たい",
        reranker=reranker,
    )

    assert result.should_show_panel is True
    assert reranker.calls
    ids = [item.capability_id for item in result.candidates]
    assert ids[0] == "weekly"
    assert "weekly" in ids


@pytest.mark.asyncio
async def test_native_ticket_action_is_local_and_never_needs_jev_authorization():
    reranker = RecordingReranker()

    result = await discover_message_capabilities(
        "管理人に問い合わせたい",
        reranker=reranker,
    )

    assert result.should_show_panel is True
    assert result.source == "local_ticket_intent"
    assert result.confidence == 1.0
    assert [item.capability_id for item in result.candidates] == ["ticket_create"]
    assert reranker.calls == []


@pytest.mark.asyncio
async def test_ticket_explanation_request_remains_normal_chat():
    reranker = RecordingReranker()

    result = await discover_message_capabilities(
        "Ticket Toolとは何？説明して",
        reranker=reranker,
    )

    assert result.should_show_panel is False
    assert reranker.calls == []


@pytest.mark.asyncio
async def test_no_local_candidate_preserves_normal_chat_fallback():
    reranker = RecordingReranker()

    result = await discover_message_capabilities(
        "サーバー設定を表示したい",
        reranker=reranker,
    )

    assert result.should_show_panel is False
    assert result.source == "gate_rejected"
    assert reranker.calls == []
