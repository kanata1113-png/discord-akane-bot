from types import SimpleNamespace

from views.event_view import EventView
from views.ticket_view import TicketCloseView, TicketView, safe_channel_name


def custom_ids(view):
    return {item.custom_id for item in view.children if item.custom_id}


def test_event_view_is_persistent_with_stable_custom_ids():
    view = EventView()

    assert view.timeout is None
    assert custom_ids(view) == {"ev_join", "ev_leave"}


def test_ticket_panel_is_persistent_with_stable_custom_ids():
    view = TicketView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {
        "ticket_category_select",
        "ticket_staff_settings",
    }


def test_ticket_controls_are_persistent_and_preserve_legacy_close_id():
    view = TicketCloseView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {
        "ticket_close_button",
        "ticket_claim_button",
        "ticket_reopen_button",
        "ticket_manage_button",
    }


def test_safe_channel_name_supports_ticket_rename_labels():
    assert safe_channel_name("Akane User") == "akaneuser"
    assert safe_channel_name("---___") == "ticket"
    assert safe_channel_name("表自派-茜") == "表自派-茜"
    assert len(safe_channel_name("a" * 100)) == 70
