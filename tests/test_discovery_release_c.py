from services.capability_catalog import DISCOVERY_RELEASE_C_SPECS
from services.capability_discovery import discover_locally, should_attempt_discovery


def _ids(text: str):
    decision = discover_locally(text, DISCOVERY_RELEASE_C_SPECS)
    return decision.should_route, [candidate.capability_id for candidate in decision.candidates]


def test_release_c_discovers_new_read_capabilities():
    routed, ids = _ids("レベルランキングを見たい")
    assert routed is True
    assert "leaderboard" in ids

    routed, ids = _ids("称号を確認したい")
    assert routed is True
    assert "titles" in ids

    routed, ids = _ids("メモリーを確認したい")
    assert routed is True
    assert "memory_status" in ids


def test_release_c_discovers_ai_capability_candidates_without_execution_policy_change():
    routed, ids = _ids("これを翻訳してほしい")
    assert routed is True
    assert "translate" in ids

    routed, ids = _ids("発言を要約してほしい")
    assert routed is True
    assert "summary" in ids

    routed, ids = _ids("辞書を使いたい")
    assert routed is True
    assert "define" in ids


def test_chat_explanation_phrasing_still_falls_back_to_ai_chat():
    assert should_attempt_discovery("翻訳について教えて") is False
    assert should_attempt_discovery("記憶とは何か教えて") is False
    assert should_attempt_discovery("ランキングについて分析して") is False
