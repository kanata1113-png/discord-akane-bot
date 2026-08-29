from ai_manager import AiManager
from config import Config


def manager_without_client():
    return AiManager.__new__(AiManager)


def test_normal_chat_route():
    model, effort, route = manager_without_client().select_chat_model("今日は何してたん？")
    assert (model, effort, route) == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )


def test_regulation_route():
    model, effort, route = manager_without_client().select_chat_model(
        "表現規制と憲法について教えて"
    )
    assert (model, effort, route) == (
        Config.REASONING_MODEL,
        Config.REASONING_EFFORT,
        "regulation",
    )


def test_reasoning_route():
    model, effort, route = manager_without_client().select_chat_model(
        "この制度のメリットとデメリットを比較して"
    )
    assert (model, effort, route) == (
        Config.REASONING_MODEL,
        Config.REASONING_EFFORT,
        "reasoning",
    )


def test_deep_reasoning_keeps_medium_effort_for_budget():
    model, effort, route = manager_without_client().select_chat_model(
        "この問題を多角的に徹底的に分析して"
    )
    assert (model, effort, route) == (
        Config.REASONING_MODEL,
        Config.DEEP_REASONING_EFFORT,
        "deep-reasoning",
    )
    assert effort == "medium"


def test_long_question_route_at_350_characters():
    model, effort, route = manager_without_client().select_chat_model("あ" * 350)
    assert (model, effort, route) == (
        Config.REASONING_MODEL,
        Config.REASONING_EFFORT,
        "long-question",
    )


def test_short_question_below_boundary_stays_normal():
    model, effort, route = manager_without_client().select_chat_model("あ" * 349)
    assert (model, effort, route) == (
        Config.CHAT_MODEL,
        Config.CHAT_REASONING_EFFORT,
        "normal-chat",
    )
