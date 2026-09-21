import pytest

from services.ai_capabilities import (
    DEFINE_SPEC,
    SUMMARY_SPEC,
    TRANSLATE_SPEC,
    build_ai_capability_dispatcher,
    dispatch_define,
    dispatch_summary,
    dispatch_translate,
)


class FakeAI:
    def __init__(self):
        self.calls = []

    async def translate(self, text, language):
        self.calls.append(("translate", text, language))
        return f"{language}:{text}"

    async def define_word(self, word, wiki_mode=False):
        self.calls.append(("define", word, wiki_mode))
        return f"definition:{word}:{wiki_mode}"

    async def summarize(self, messages):
        self.calls.append(("summary", tuple(messages)))
        return "summary-result"


def test_ai_specs_track_external_cost_without_write_risk():
    for spec in (TRANSLATE_SPEC, DEFINE_SPEC, SUMMARY_SPEC):
        assert spec.incurs_external_cost is True
        assert spec.requires_confirmation is False


@pytest.mark.asyncio
async def test_translate_dispatch_preserves_arguments():
    source = FakeAI()
    dispatcher = build_ai_capability_dispatcher(source)

    result = await dispatch_translate(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        text="hello",
        language="ja",
    )

    assert result.value == {"text": "ja:hello", "language": "ja"}
    assert source.calls == [("translate", "hello", "ja")]


@pytest.mark.asyncio
async def test_define_dispatch_preserves_wiki_mode():
    source = FakeAI()
    dispatcher = build_ai_capability_dispatcher(source)

    result = await dispatch_define(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        word="liberty",
        wiki_mode=True,
    )

    assert result.value["wiki_mode"] is True
    assert source.calls == [("define", "liberty", True)]


@pytest.mark.asyncio
async def test_summary_dispatch_preserves_message_order():
    source = FakeAI()
    dispatcher = build_ai_capability_dispatcher(source)

    result = await dispatch_summary(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        messages=["old", "new"],
    )

    assert result.value == {"text": "summary-result"}
    assert source.calls == [("summary", ("old", "new"))]
