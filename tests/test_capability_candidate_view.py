from types import SimpleNamespace

import pytest

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


class FakeResponse:
    def __init__(self):
        self.sent = None
        self.edited = None
        self._done = False

    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        self.sent = {
            "content": content,
            "ephemeral": ephemeral,
            **kwargs,
        }
        self._done = True

    async def edit_message(self, *, content, view):
        self.edited = {
            "content": content,
            "view": view,
        }
        self._done = True

    def is_done(self):
        return self._done


class FakeMessage:
    def __init__(self):
        self.edited = None

    async def edit(self, *, content, view):
        self.edited = {
            "content": content,
            "view": view,
        }


class FakeInteraction:
    def __init__(self, user_id):
        self.user = SimpleNamespace(id=user_id)
        self.response = FakeResponse()
        self.message = FakeMessage()


def test_panel_caps_candidate_buttons_at_four_and_contains_no_dispatcher():
    candidates = tuple(
        candidate(f"cap{i}", f"候補{i}", f"/cap{i}")
        for i in range(6)
    )
    view = CapabilityCandidateView(candidates, requester_id=123)

    assert len(view.children) == 5
    assert [item.custom_id for item in view.children[:4]] == [
        "cap_discovery:cap0",
        "cap_discovery:cap1",
        "cap_discovery:cap2",
        "cap_discovery:cap3",
    ]
    assert view.children[4].custom_id == "cap_discovery:cancel"
    assert view.children[4].label == "キャンセル"
    assert view.cancelled is False
    assert not hasattr(view, "dispatcher")
    assert not hasattr(view, "handler")


def test_panel_copy_explains_approved_reads_execute_after_selection():
    text = candidate_panel_text(
        (candidate("weekly", "今週のXPランキング", "/weekly"),)
    )

    assert "選択後にそのまま実行" in text


def test_buttons_are_existing_capability_metadata_only():
    weekly = candidate("weekly", "今週のXPランキング", "/weekly")
    view = CapabilityCandidateView((weekly,), requester_id=123)

    assert view.selection is None
    assert view.children[0].label == "今週のXPランキング"
    assert view.children[0].custom_id == "cap_discovery:weekly"
    assert view.children[1].custom_id == "cap_discovery:cancel"


@pytest.mark.asyncio
async def test_explicit_selection_invokes_execution_callback_once_and_disables_panel():
    weekly = candidate("weekly", "今週のXPランキング", "/weekly")
    calls = []

    async def execute(interaction, selection):
        calls.append((interaction.user.id, selection.capability_id))
        await interaction.response.send_message("result", ephemeral=True)
        return True

    view = CapabilityCandidateView(
        (weekly,),
        requester_id=123,
        on_select=execute,
    )
    interaction = FakeInteraction(user_id=123)

    assert await view.interaction_check(interaction) is True
    await view._select(interaction, weekly)

    assert calls == [(123, "weekly")]
    assert view.selection.capability_id == "weekly"
    assert view.cancelled is False
    assert all(item.disabled for item in view.children)
    assert view.is_finished()
    assert interaction.message.edited["view"] is view
    assert "実行済み" in interaction.message.edited["content"]


@pytest.mark.asyncio
async def test_selection_only_mode_remains_available_explicitly():
    weekly = candidate("weekly", "今週のXPランキング", "/weekly")
    view = CapabilityCandidateView(
        (weekly,),
        requester_id=123,
        on_select=None,
    )
    interaction = FakeInteraction(user_id=123)

    await view._select(interaction, weekly)

    assert view.selection.capability_id == "weekly"
    assert "まだ自動実行はしてへん" in interaction.response.edited["content"]
    assert all(item.disabled for item in view.children)


@pytest.mark.asyncio
async def test_non_executable_selection_fails_closed_without_execution_result():
    rankings = candidate("rankings", "サーバー内ランキング", "/rankings")

    async def reject(interaction, selection):
        return False

    view = CapabilityCandidateView(
        (rankings,),
        requester_id=123,
        on_select=reject,
    )
    interaction = FakeInteraction(user_id=123)

    await view._select(interaction, rankings)

    assert view.selection.capability_id == "rankings"
    assert interaction.response.sent is None
    assert "直接実行対象外" in interaction.response.edited["content"]
    assert all(item.disabled for item in view.children)


@pytest.mark.asyncio
async def test_cancel_is_requester_only():
    view = CapabilityCandidateView(
        (candidate("weekly", "今週のXPランキング", "/weekly"),),
        requester_id=123,
    )
    interaction = FakeInteraction(user_id=999)

    allowed = await view.interaction_check(interaction)

    assert allowed is False
    assert interaction.response.sent == {
        "content": "この候補はリクエストした本人だけ選べるで。",
        "ephemeral": True,
    }
    assert view.cancelled is False
    assert view.selection is None
    assert all(not item.disabled for item in view.children)


@pytest.mark.asyncio
async def test_cancel_stops_panel_without_selection_or_execution():
    calls = []

    async def execute(interaction, selection):
        calls.append(selection.capability_id)
        return True

    view = CapabilityCandidateView(
        (candidate("weekly", "今週のXPランキング", "/weekly"),),
        requester_id=123,
        on_select=execute,
    )
    interaction = FakeInteraction(user_id=123)

    assert await view.interaction_check(interaction) is True
    await view._cancel(interaction)

    assert calls == []
    assert view.cancelled is True
    assert view.selection is None
    assert all(item.disabled for item in view.children)
    assert view.is_finished()
    assert interaction.response.edited["view"] is view
    assert "キャンセル済み" in interaction.response.edited["content"]
    assert "処理はここで終了" in interaction.response.edited["content"]
    assert not hasattr(view, "dispatcher")
    assert not hasattr(view, "handler")
