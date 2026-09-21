from views.capability_candidate_view import PARAMETERIZED_DISCOVERY_IDS
from views.parameterized_capability_view import ParameterizedCapabilityEntryView, RankingsView


def test_parameterized_candidate_set_is_exact():
    assert PARAMETERIZED_DISCOVERY_IDS == frozenset({
        "message_search",
        "translate",
        "define",
        "summary",
        "rankings",
        "fortune",
        "titles",
    })


def test_parameterized_entry_declares_same_supported_set():
    assert ParameterizedCapabilityEntryView.SUPPORTED == PARAMETERIZED_DISCOVERY_IDS


def test_rankings_choices_match_capability_categories():
    assert RankingsView.CHOICES == (
        ("🔥 週間XP", "weekly"),
        ("💬 発言数", "messages"),
        ("🤖 AI会話", "ai"),
        ("🏆 実績数", "achievements"),
    )


def test_write_confirm_capabilities_are_not_parameterized_read_flows():
    assert PARAMETERIZED_DISCOVERY_IDS.isdisjoint({
        "title_set", "memory_forget", "remind", "event_create", "poll_create"
    })
