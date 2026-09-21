from __future__ import annotations

from typing import Protocol, Sequence

from services.capability_core import (
    CapabilityContext,
    CapabilityDispatcher,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityRisk,
    CapabilitySpec,
)


TRANSLATE_CAPABILITY_ID = "translate"
DEFINE_CAPABILITY_ID = "define"
SUMMARY_CAPABILITY_ID = "summary"

TRANSLATE_SPEC = CapabilitySpec(
    capability_id=TRANSLATE_CAPABILITY_ID,
    name="AI翻訳",
    description="指定した文章をAIで翻訳する",
    risk=CapabilityRisk.READ_ONLY,
    category="ai",
    slash_command="/translate",
    incurs_external_cost=True,
    tags=("translate", "translation", "翻訳"),
)

DEFINE_SPEC = CapabilitySpec(
    capability_id=DEFINE_CAPABILITY_ID,
    name="AI辞書",
    description="単語や概念をAIで説明する",
    risk=CapabilityRisk.READ_ONLY,
    category="ai",
    slash_command="/define",
    incurs_external_cost=True,
    tags=("define", "dictionary", "辞書", "意味"),
)

SUMMARY_SPEC = CapabilitySpec(
    capability_id=SUMMARY_CAPABILITY_ID,
    name="発言要約",
    description="自分の直近の発言をAIで要約する",
    risk=CapabilityRisk.READ_ONLY,
    category="ai",
    slash_command="/summary",
    incurs_external_cost=True,
    tags=("summary", "summarize", "要約"),
)


class AICapabilityDataSource(Protocol):
    async def translate(self, text: str, language: str) -> str:
        ...

    async def define_word(self, word: str, wiki_mode: bool = False) -> str:
        ...

    async def summarize(self, messages: Sequence[str]) -> str:
        ...


async def translate_handler(
    data_source: AICapabilityDataSource,
    context: CapabilityContext,
    *,
    text: str,
    language: str,
) -> CapabilityResult:
    result = await data_source.translate(text, language)
    return CapabilityResult(
        TRANSLATE_CAPABILITY_ID,
        True,
        value={"text": result, "language": language},
    )


async def define_handler(
    data_source: AICapabilityDataSource,
    context: CapabilityContext,
    *,
    word: str,
    wiki_mode: bool,
) -> CapabilityResult:
    result = await data_source.define_word(word, wiki_mode)
    return CapabilityResult(
        DEFINE_CAPABILITY_ID,
        True,
        value={"text": result, "word": word, "wiki_mode": wiki_mode},
    )


async def summary_handler(
    data_source: AICapabilityDataSource,
    context: CapabilityContext,
    *,
    messages: Sequence[str],
) -> CapabilityResult:
    result = await data_source.summarize(messages)
    return CapabilityResult(
        SUMMARY_CAPABILITY_ID,
        True,
        value={"text": result},
    )


def build_ai_capability_dispatcher(
    data_source: AICapabilityDataSource,
) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in (TRANSLATE_SPEC, DEFINE_SPEC, SUMMARY_SPEC):
        registry.register(spec)

    dispatcher = CapabilityDispatcher(registry)

    async def handle_translate(context, arguments):
        return await translate_handler(
            data_source,
            context,
            text=str(arguments["text"]),
            language=str(arguments["language"]),
        )

    async def handle_define(context, arguments):
        return await define_handler(
            data_source,
            context,
            word=str(arguments["word"]),
            wiki_mode=bool(arguments["wiki_mode"]),
        )

    async def handle_summary(context, arguments):
        return await summary_handler(
            data_source,
            context,
            messages=tuple(str(item) for item in arguments["messages"]),
        )

    dispatcher.register_handler(TRANSLATE_CAPABILITY_ID, handle_translate)
    dispatcher.register_handler(DEFINE_CAPABILITY_ID, handle_define)
    dispatcher.register_handler(SUMMARY_CAPABILITY_ID, handle_summary)
    return dispatcher


def _context(*, user_id: int, guild_id: int | None, channel_id: int | None):
    return CapabilityContext(
        user_id=user_id,
        guild_id=guild_id,
        channel_id=channel_id,
    )


async def dispatch_translate(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
    text: str,
    language: str,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            TRANSLATE_CAPABILITY_ID,
            {"text": text, "language": language},
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_define(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
    word: str,
    wiki_mode: bool,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            DEFINE_CAPABILITY_ID,
            {"word": word, "wiki_mode": wiki_mode},
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_summary(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
    messages: Sequence[str],
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(SUMMARY_CAPABILITY_ID, {"messages": tuple(messages)}),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )
