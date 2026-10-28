from config import Config
from services.routing_policy import RoutingPolicy


def selection_tuple(content: str) -> tuple[str, str, str]:
    selection = RoutingPolicy.legacy_selection(content)
    return selection.model, selection.reasoning_effort, selection.route


def test_normal_chat_route():
    assert selection_tuple("今日は何してたん？") == (
        Config.FAST_MODEL,
        Config.FAST_REASONING_EFFORT,
        "normal-chat",
    )


def test_regulation_route():
    assert selection_tuple("表現規制と憲法について教えて") == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "regulation",
    )


def test_reasoning_route():
    assert selection_tuple("この制度のメリットとデメリットを比較して") == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "reasoning",
    )


def test_deep_reasoning_keeps_medium_effort_for_budget():
    model, effort, route = selection_tuple("この問題を多角的に徹底的に分析して")
    assert (model, effort, route) == (
        Config.REASONING_MODEL,
        Config.DEEP_REASONING_EFFORT,
        "deep-reasoning",
    )
    assert effort == "medium"


def test_long_question_route_at_350_characters():
    assert selection_tuple("あ" * 350) == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "long-question",
    )


def test_short_question_below_boundary_stays_normal():
    assert selection_tuple("あ" * 349) == (
        Config.FAST_MODEL,
        Config.FAST_REASONING_EFFORT,
        "normal-chat",
    )
