import pytest

from services.jev_discovery_reranker import DiscoveryRerankResult
from services.message_capability_discovery import discover_message_capabilities


class LocalOrderReranker:
    async def rerank(self, content, candidates):
        return DiscoveryRerankResult(
            tuple(candidates),
            False,
            0.0,
            0,
            "local_fallback",
        )


POSITIVE_CASES = (
    ("自分のレベルを見たい", "level"),
    ("レベルを確認したい", "level"),
    ("今週のXPランキングを見たい", "weekly"),
    ("ランキングを表示して", "rankings"),
    ("プロフィールを表示したい", "profile"),
    ("実績を確認したい", "achievements"),
    ("今日の運勢を占いたい", "fortune"),
)

NEGATIVE_CASES = (
    "今日はいい天気だね",
    "どう思う？",
    "なぜランキング制度が必要なの？",
    "レベルの高い議論だね",
    "プロフィール記事について分析して",
    "実績のある政治家について教えて",
    "運勢って科学的に意味あるの？",
    "XPという言葉の意味を教えて",
    "ランキング文化についてどう思う？",
    "今週は忙しかった",
)


@pytest.mark.asyncio
@pytest.mark.parametrize(("text", "expected"), POSITIVE_CASES)
async def test_discovery_positive_corpus(text, expected):
    result = await discover_message_capabilities(
        text,
        reranker=LocalOrderReranker(),
    )

    assert result.should_show_panel is True
    assert result.candidates[0].capability_id == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("text", NEGATIVE_CASES)
async def test_discovery_negative_corpus_preserves_chat(text):
    result = await discover_message_capabilities(
        text,
        reranker=LocalOrderReranker(),
    )

    assert result.should_show_panel is False
