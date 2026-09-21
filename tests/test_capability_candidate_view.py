from services.capability_discovery import DiscoveryCandidate
from views.capability_candidate_view import (
    CapabilityCandidateView,
    candidate_panel_text,
)


def candidate(capability_id, name, command):
    return DiscoveryCandidate(
        capability_id=capability_id,
        name=name,
        description=f"{name} description",
        slash_command=command,
        score=1.0,
        matched_terms=(capability_id,),
    )


def test_panel_caps_buttons_at_four_and_contains_no_dispatcher():
    candidates = tuple(
        candidate(f"cap{i}", f"候補{i}", f"/cap{i}")
        for i in range(6)
    )
    view = CapabilityCandidateView(candidates, requester_id=123)

    assert len(view.children) == 4
    assert [item.custom_id for item in view.children] == [
        "cap_discovery:cap0",
        "cap_discovery:cap1",
        "cap_discovery:cap2",
        "cap_discovery:cap3",
    ]
    assert not hasattr(view, "dispatcher")
    assert not hasattr(view, "handler")


def test_panel_copy_explicitly_says_selection_does_not_execute():
    text = candidate_panel_text(
        (candidate("weekly", "今週のXPランキング", "/weekly"),)
    )

    assert "自動実行されへん" in text


def test_buttons_are_existing_capability_metadata_only():
    weekly = candidate("weekly", "今週のXPランキング", "/weekly")
    view = CapabilityCandidateView((weekly,), requester_id=123)

    assert view.selection is None
    assert view.children[0].label == "今週のXPランキング"
    assert view.children[0].custom_id == "cap_discovery:weekly"
