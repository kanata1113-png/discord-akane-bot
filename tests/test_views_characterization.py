from types import SimpleNamespace

from views.event_view import EventView
from views.ticket_view import TicketCloseView, TicketClosedView, TicketView, safe_channel_name


def custom_ids(view):
    return {item.custom_id for item in view.children if item.custom_id}


def test_event_view_is_persistent_with_stable_custom_ids():
    view = EventView()

    assert view.timeout is None
    assert custom_ids(view) == {"ev_join", "ev_leave"}


def test_ticket_panel_is_persistent_with_stable_custom_id():
    view = TicketView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {"ticket_category_select"}


def test_ticket_close_view_is_persistent_with_stable_custom_id():
    view = TicketCloseView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {
        "ticket_close_button",
        "ticket_claim_button",
        "ticket_rename_button",
        "ticket_add_member_button",
        "ticket_remove_member_button",
    }


def test_ticket_closed_view_is_persistent_with_reopen_and_delete():
    view = TicketClosedView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {
        "ticket_reopen_button",
        "ticket_delete_button",
    }


def test_safe_channel_name_current_behavior():
    assert safe_channel_name("Akane User") == "akaneuser"
    assert safe_channel_name("---___") == "user"
    assert safe_channel_name("表自派-茜") == "表自派-茜"
    assert len(safe_channel_name("a" * 50)) == 30
