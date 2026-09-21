from services.capability_discovery import (
    discover_locally,
    shortlist_capabilities,
    should_attempt_discovery,
)
from services.progression_capabilities import (
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
    LEVEL_SPEC,
    PROFILE_SPEC,
    RANKINGS_SPEC,
    WEEKLY_SPEC,
)


SPECS = (
    LEVEL_SPEC,
    WEEKLY_SPEC,
    RANKINGS_SPEC,
    PROFILE_SPEC,
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
)


def test_gate_accepts_action_like_progression_requests():
    assert should_attempt_discovery("今週一番活動してる人をランキングで見たい")
    assert should_attempt_discovery("自分のレベルを確認したい")
    assert should_attempt_discovery("今日の運勢を占いたい")


def test_gate_rejects_ordinary_chat_and_analysis():
    assert not should_attempt_discovery("今日はいい天気だね")
    assert not should_attempt_discovery("どう思う？")
    assert not should_attempt_discovery("なぜランキング制度が必要なの？")


def test_shortlist_prefers_specific_capability_terms():
    candidates = shortlist_capabilities("自分のレベルとXPを見たい", SPECS)

    assert candidates
    assert candidates[0].capability_id == "level"
    assert candidates[0].slash_command == "/level"


def test_weekly_request_surfaces_weekly_and_related_ranking_candidates():
    candidates = shortlist_capabilities("今週のXPランキングを見たい", SPECS)

    ids = [candidate.capability_id for candidate in candidates]
    assert ids[0] == "weekly"
    assert "rankings" in ids


def test_local_discovery_fails_closed_when_no_capability_matches():
    decision = discover_locally("サーバーの設定を見たい", SPECS)

    assert decision.should_route is False
    assert decision.candidates == ()
    assert decision.reason == "no_local_candidate"


def test_local_discovery_does_not_execute_any_capability():
    decision = discover_locally("プロフィールを表示したい", SPECS)

    assert decision.should_route is True
    assert decision.reason == "local_candidate"
    assert decision.candidates[0].capability_id == "profile"
    assert all(hasattr(item, "score") for item in decision.candidates)
