import pytest

from cogs.community_v4 import _clean_search_text, _query_relevant_snippet
from database import DatabaseManager
from db_migrations import run_migrations
from repositories import RepositoryRegistry
from services.message_capability_discovery import discover_ticket_intent
from views.community_write_view import (
    EventChannelSelectView,
    EventTypeChoiceView,
    _normalize_date,
    _normalize_optional_end,
    _normalize_time,
)
from views.ticket_view import TicketCloseView, TicketView


def test_search_snippet_is_compact_and_query_relevant():
    text = "## 前置きです。これは長い説明です。 **誹謗中傷** への対応を考える必要があります。さらに後文があります。"
    snippet = _query_relevant_snippet(text, "誹謗中傷")

    assert "誹謗中傷" in snippet
    assert "##" not in snippet
    assert "**" not in snippet
    assert len(snippet) <= 67
    assert "\n" not in _clean_search_text("a\nb")


def test_event_wizard_orders_voice_stage_external_and_uses_channel_select():
    view = EventTypeChoiceView(requester_id=1)
    labels = [item.label for item in view.children[:3]]
    assert labels == ["🔊 ボイス", "🎙️ ステージ", "🌐 その他 / 外部"]

    voice = EventChannelSelectView(requester_id=1, event_type="voice")
    assert voice.children[0].custom_id == "event_channel:voice"
    assert "ボイス" in voice.children[0].placeholder

    stage = EventChannelSelectView(requester_id=1, event_type="stage")
    assert stage.children[0].custom_id == "event_channel:stage"
    assert "ステージ" in stage.children[0].placeholder


def test_event_datetime_helpers_remove_half_width_space_memorization():
    assert _normalize_date("2026-9-22") == "2026/09/22"
    assert _normalize_time("1800") == "18:00"
    assert _normalize_time("18：00") == "18:00"
    assert _normalize_optional_end("2200", start_date="2026/09/22") == "2026/09/22 22:00"
    assert _normalize_optional_end("2026-09-23 01:00", start_date="2026/09/22") == "2026/09/23 01:00"


def test_ticket_intent_is_action_specific():
    candidate = discover_ticket_intent("管理人に問い合わせたい")
    assert candidate is not None
    assert candidate.capability_id == "ticket_create"
    assert discover_ticket_intent("Ticket Toolとは何？説明して") is None
    assert discover_ticket_intent("管理人って何をする人？") is None


def test_ticket_views_expose_native_persistent_operations():
    bot = object()
    panel = TicketView(bot)
    panel_ids = {item.custom_id for item in panel.children if item.custom_id}
    assert panel.timeout is None
    assert {"ticket_category_select", "ticket_staff_settings"} <= panel_ids

    controls = TicketCloseView(bot)
    ids = {item.custom_id for item in controls.children if item.custom_id}
    assert controls.timeout is None
    assert ids == {
        "ticket_close_button",
        "ticket_claim_button",
        "ticket_reopen_button",
        "ticket_manage_button",
    }


@pytest.mark.asyncio
async def test_native_ticket_repository_round_trip_after_additive_migration(tmp_path):
    db_path = tmp_path / "akane.db"
    manager = DatabaseManager(str(db_path))
    await manager.init()
    await run_migrations(str(db_path))
    repos = RepositoryRegistry(str(db_path))

    number1 = await repos.tickets.reserve_number(1)
    number2 = await repos.tickets.reserve_number(1)
    assert (number1, number2) == (1, 2)

    ticket_id = await repos.tickets.create(
        1,
        20,
        30,
        "admin",
        ticket_number=number1,
        subject="管理人への相談",
    )
    native = await repos.tickets.get_native_by_channel(20)
    assert native[0] == ticket_id
    assert native[8] == 1
    assert native[9] == "管理人への相談"

    await repos.tickets.set_staff_role(1, 999)
    settings = await repos.tickets.get_settings(1)
    assert settings[1] == 999

    await repos.tickets.claim(20, 88)
    native = await repos.tickets.get_native_by_channel(20)
    assert native[10] == 88

    await repos.tickets.add_member(ticket_id, 77)
    assert await repos.tickets.list_members(ticket_id) == [(77,)]
    await repos.tickets.remove_member(ticket_id, 77)
    assert await repos.tickets.list_members(ticket_id) == []

    await repos.tickets.close(20)
    assert (await repos.tickets.get_native_by_channel(20))[5] == "closed"
    await repos.tickets.reopen(20)
    assert (await repos.tickets.get_native_by_channel(20))[5] == "open"

    await repos.tickets.audit(
        ticket_id=ticket_id,
        guild_id=1,
        channel_id=20,
        actor_id=88,
        action="claim",
        detail=None,
    )
    audit = await repos.store.fetchone(
        "SELECT action, actor_id FROM ticket_audit WHERE ticket_id=?",
        (ticket_id,),
    )
    assert audit == ("claim", 88)
