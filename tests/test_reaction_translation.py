from types import SimpleNamespace

import pytest

from config import Config
from services.capability_core import CapabilityRisk
from services.reaction_translation import (
    REACTION_TRANSLATE_SPEC,
    ReactionTranslationService,
)
from views.reaction_translation_view import (
    FULL_TRANSLATION_CUSTOM_ID,
    ReactionTranslationView,
)


class FakeAI:
    def __init__(self):
        self.calls = []

    async def translate(self, text, language):
        self.calls.append((text, language))
        return f"translated:{language}:{text}"


def custom_ids(view):
    return {item.custom_id for item in view.children if item.custom_id}


def test_reaction_translate_is_event_only_read_only_external_cost_capability():
    assert REACTION_TRANSLATE_SPEC.capability_id == "reaction_translate"
    assert REACTION_TRANSLATE_SPEC.risk is CapabilityRisk.READ_ONLY
    assert REACTION_TRANSLATE_SPEC.incurs_external_cost is True
    assert REACTION_TRANSLATE_SPEC.discoverable is False
    assert REACTION_TRANSLATE_SPEC.slash_command is None


def test_flag_mapping_is_deterministic_and_local():
    assert ReactionTranslationService.language_for_flag("🇺🇸") == "English"
    assert ReactionTranslationService.language_for_flag("🇬🇧") == "English"
    assert ReactionTranslationService.language_for_flag("🇯🇵") == "Japanese"
    assert ReactionTranslationService.language_for_flag("🦊") is None


def test_preview_is_compact_and_whitespace_normalized():
    text = "hello\n\nworld   " + ("x" * 200)
    preview = ReactionTranslationService.preview(text, 140)

    assert "\n" not in preview
    assert len(preview) <= 140
    assert preview.endswith("…")


@pytest.mark.asyncio
async def test_translation_cache_avoids_duplicate_luna_calls():
    ai = FakeAI()
    service = ReactionTranslationService(SimpleNamespace(ai=ai))

    first = await service.translate("こんにちは", "English")
    second = await service.translate("こんにちは", "English")

    assert first == second
    assert ai.calls == [("こんにちは", "English")]


@pytest.mark.asyncio
async def test_translation_cache_separates_target_languages():
    ai = FakeAI()
    service = ReactionTranslationService(SimpleNamespace(ai=ai))

    await service.translate("こんにちは", "English")
    await service.translate("こんにちは", "French")

    assert len(ai.calls) == 2


def test_rate_limit_is_per_user_and_windowed(monkeypatch):
    monkeypatch.setattr(Config, "REACTION_TRANSLATION_RATE_LIMIT", 2)
    monkeypatch.setattr(Config, "REACTION_TRANSLATION_RATE_WINDOW_SECONDS", 60)
    service = ReactionTranslationService(SimpleNamespace(ai=FakeAI()))

    assert service.allow_user(1, now=100.0) is True
    assert service.allow_user(1, now=110.0) is True
    assert service.allow_user(1, now=120.0) is False
    assert service.allow_user(2, now=120.0) is True
    assert service.allow_user(1, now=161.0) is True


def test_full_translation_button_is_persistent():
    view = ReactionTranslationView(SimpleNamespace())

    assert view.timeout is None
    assert custom_ids(view) == {FULL_TRANSLATION_CUSTOM_ID}


def test_card_tracking_detects_edited_source():
    service = ReactionTranslationService(SimpleNamespace(ai=FakeAI()))
    service.remember_card(
        source_message_id=10,
        language="English",
        card_message_id=99,
        source_text="original",
    )

    assert service.card_is_current(10, "English", "original") is True
    assert service.card_is_current(10, "English", "edited") is False
