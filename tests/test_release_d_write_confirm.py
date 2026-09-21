from types import SimpleNamespace

import pytest

from services.capability_catalog import DISCOVERY_RELEASE_D_SPECS
from services.capability_discovery import discover_locally
from services.discovery_execution_policy import DIRECT_EXECUTION_CAPABILITY_IDS
from services.write_intent_discovery import discover_write_intent
from views.capability_candidate_view import (
    CapabilityCandidateView,
    WRITE_CONFIRM_DISCOVERY_IDS,
)
from views.write_capability_view import WriteCapabilityEntryView


@pytest.mark.parametrize(
    ("text", "capability_id"),
    [
        ("称号を変更して", "title_set"),
        ("記憶を消して", "memory_forget"),
        ("リマインダーを登録したい", "remind"),
    ],
)
def test_write_intent_gate_routes_only_supported_pilot(text, capability_id):
    decision = discover_write_intent(text)
    assert decision.should_route is True
    assert decision.capability_id == capability_id


def test_write_intent_gate_rejects_read_or_chat_phrasing():
    assert discover_write_intent("称号を見たい").should_route is False
    assert discover_write_intent("記憶について教えて").should_route is False
    assert discover_write_intent("リマインダー文化についてどう思う").should_route is False


@pytest.mark.parametrize(
    ("text", "capability_id"),
    [
        ("称号を変更して", "title_set"),
        ("記憶を消して", "memory_forget"),
        ("リマインダーを登録したい", "remind"),
    ],
)
def test_write_capability_is_ranked_first(text, capability_id):
    decision = discover_locally(text, DISCOVERY_RELEASE_D_SPECS)
    assert decision.should_route is True
    assert decision.candidates[0].capability_id == capability_id


def test_release_d_write_ids_are_not_direct_execution_ids():
    assert WRITE_CONFIRM_DISCOVERY_IDS == frozenset(
        {"title_set", "memory_forget", "remind"}
    )
    assert WRITE_CONFIRM_DISCOVERY_IDS.isdisjoint(
        DIRECT_EXECUTION_CAPABILITY_IDS
    )


def test_write_entry_view_has_explicit_select_and_cancel_controls():
    view = WriteCapabilityEntryView(
        requester_id=123,
        capability_id="memory_forget",
        capability_name="会話履歴削除",
    )
    custom_ids = {item.custom_id for item in view.children}
    assert custom_ids == {
        "write_entry:memory_forget",
        "write_entry:cancel",
    }


def test_candidate_panel_routes_write_capability_without_expanding_direct_executor():
    candidate = SimpleNamespace(
        capability_id="title_set",
        name="称号変更",
        description="プロフィールの称号を変更",
        slash_command="/title_set",
    )
    view = CapabilityCandidateView([candidate], requester_id=123)
    assert view.children[0].custom_id == "cap_discovery:title_set"
    assert "title_set" not in DIRECT_EXECUTION_CAPABILITY_IDS
