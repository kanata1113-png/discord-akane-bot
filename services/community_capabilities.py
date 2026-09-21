from __future__ import annotations

from typing import Any, Protocol

from services.capability_core import (
    CapabilityContext,
    CapabilityDispatcher,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityRisk,
    CapabilitySpec,
)


MESSAGE_SEARCH_CAPABILITY_ID = "message_search"
EVENT_CREATE_CAPABILITY_ID = "event_create"
POLL_CREATE_CAPABILITY_ID = "poll_create"

MESSAGE_SEARCH_SPEC = CapabilitySpec(
    capability_id=MESSAGE_SEARCH_CAPABILITY_ID,
    name="メッセージ検索",
    description="サーバー内のメッセージを条件指定で検索する",
    risk=CapabilityRisk.READ_ONLY,
    category="community",
    slash_command="/search",
    tags=("search", "検索", "メッセージ"),
)

EVENT_CREATE_SPEC = CapabilitySpec(
    capability_id=EVENT_CREATE_CAPABILITY_ID,
    name="イベント作成",
    description="Discord公式スケジュールイベントを作成する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="community",
    slash_command="/event_create",
    requires_confirmation=True,
    tags=("event", "イベント", "予定", "スケジュール"),
)

POLL_CREATE_SPEC = CapabilitySpec(
    capability_id=POLL_CREATE_CAPABILITY_ID,
    name="投票作成",
    description="質問と選択肢からDiscord投票を作成する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="community",
    slash_command="/poll",
    requires_confirmation=True,
    tags=("poll", "投票", "アンケート"),
)


class CommunityCapabilityDataSource(Protocol):
    async def search_messages(self, *, context: CapabilityContext, keyword: str, target_channel_id: int | None, target_user_id: int | None, days: int | None) -> Any: ...

    async def create_event(
        self,
        *,
        context: CapabilityContext,
        name: str,
        start: str,
        end: str | None,
        event_type: str,
        location: str | None,
        event_channel_id: int | None,
        description: str | None,
    ) -> Any: ...

    async def create_poll(self, *, context: CapabilityContext, question: str, options: tuple[str, ...]) -> Any: ...


async def message_search_handler(data_source, context, *, keyword, target_channel_id, target_user_id, days):
    value = await data_source.search_messages(
        context=context,
        keyword=keyword,
        target_channel_id=target_channel_id,
        target_user_id=target_user_id,
        days=days,
    )
    return CapabilityResult(MESSAGE_SEARCH_CAPABILITY_ID, True, value=value)


async def event_create_handler(
    data_source,
    context,
    *,
    name,
    start,
    end,
    event_type,
    location,
    event_channel_id,
    description,
):
    value = await data_source.create_event(
        context=context,
        name=name,
        start=start,
        end=end,
        event_type=event_type,
        location=location,
        event_channel_id=event_channel_id,
        description=description,
    )
    return CapabilityResult(EVENT_CREATE_CAPABILITY_ID, True, value=value)


async def poll_create_handler(data_source, context, *, question, options):
    value = await data_source.create_poll(
        context=context,
        question=question,
        options=tuple(options),
    )
    return CapabilityResult(POLL_CREATE_CAPABILITY_ID, True, value=value)


def build_community_capability_dispatcher(data_source: CommunityCapabilityDataSource) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in (MESSAGE_SEARCH_SPEC, EVENT_CREATE_SPEC, POLL_CREATE_SPEC):
        registry.register(spec)
    dispatcher = CapabilityDispatcher(registry)

    async def handle_search(context, arguments):
        return await message_search_handler(
            data_source, context,
            keyword=str(arguments["keyword"]),
            target_channel_id=arguments.get("target_channel_id"),
            target_user_id=arguments.get("target_user_id"),
            days=arguments.get("days"),
        )

    async def handle_event(context, arguments):
        return await event_create_handler(
            data_source,
            context,
            name=str(arguments["name"]),
            start=str(arguments["start"]),
            end=arguments.get("end"),
            event_type=str(arguments.get("event_type", "external")),
            location=arguments.get("location"),
            event_channel_id=arguments.get("event_channel_id"),
            description=arguments.get("description"),
        )

    async def handle_poll(context, arguments):
        return await poll_create_handler(
            data_source, context,
            question=str(arguments["question"]),
            options=tuple(str(item) for item in arguments["options"]),
        )

    dispatcher.register_handler(MESSAGE_SEARCH_CAPABILITY_ID, handle_search)
    dispatcher.register_handler(EVENT_CREATE_CAPABILITY_ID, handle_event)
    dispatcher.register_handler(POLL_CREATE_CAPABILITY_ID, handle_poll)
    return dispatcher


def _context(*, user_id: int, guild_id: int | None, channel_id: int | None, interaction=None):
    return CapabilityContext(
        user_id=user_id,
        guild_id=guild_id,
        channel_id=channel_id,
        interaction=interaction,
    )


async def dispatch_message_search(dispatcher, *, user_id, guild_id, channel_id, keyword, target_channel_id=None, target_user_id=None, days=None, interaction=None):
    return await dispatcher.dispatch(
        CapabilityRequest(MESSAGE_SEARCH_CAPABILITY_ID, {
            "keyword": keyword,
            "target_channel_id": target_channel_id,
            "target_user_id": target_user_id,
            "days": days,
        }),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )


async def dispatch_event_create(
    dispatcher,
    *,
    user_id,
    guild_id,
    channel_id,
    name,
    start,
    end=None,
    event_type="external",
    location=None,
    event_channel_id=None,
    description=None,
    confirmed,
    interaction=None,
):
    return await dispatcher.dispatch(
        CapabilityRequest(
            EVENT_CREATE_CAPABILITY_ID,
            {
                "name": name,
                "start": start,
                "end": end,
                "event_type": event_type,
                "location": location,
                "event_channel_id": event_channel_id,
                "description": description,
            },
            confirmed=confirmed,
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )


async def dispatch_poll_create(dispatcher, *, user_id, guild_id, channel_id, question, options, confirmed, interaction=None):
    return await dispatcher.dispatch(
        CapabilityRequest(POLL_CREATE_CAPABILITY_ID, {"question": question, "options": tuple(options)}, confirmed=confirmed),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )
