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
    ("レベルランキングを見たい", "leaderboard"),
    ("今週のXPランキングを見たい", "weekly"),
    ("ランキングを表示して", "rankings"),
    ("プロフィールを表示したい", "profile"),
    ("実績を確認したい", "achievements"),
    ("今日の運勢を占いたい", "fortune"),
    ("称号を確認したい", "titles"),
    ("メモリーを確認したい", "memory_status"),
    ("これを翻訳してほしい", "translate"),
    ("発言を要約してほしい", "summary"),
    ("辞書を使いたい", "define"),
    ("メッセージを検索したい", "message_search"),
    # WRITE_CONFIRM discovery. Candidate selection alone never performs writes.
    ("称号を変更して", "title_set"),
    ("称号を装備して", "title_set"),
    ("記憶を消して", "memory_forget"),
    ("メモリーを削除して", "memory_forget"),
    ("memoryをforgetして", "memory_forget"),
    ("リマインダーを登録して", "remind"),
    ("イベントを作って", "event_create"),
    ("投票を作って", "poll_create"),
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
    "翻訳について教えて",
    "記憶とは何か教えて",
    "辞書の歴史について教えて",
    "リマインダーについて教えて",
    "イベントについて教えて",
    "投票制度についてどう思う？",
    "検索技術について教えて",
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
