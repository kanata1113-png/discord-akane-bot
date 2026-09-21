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


TITLES_CAPABILITY_ID = "titles"
TITLE_SET_CAPABILITY_ID = "title_set"
MEMORY_STATUS_CAPABILITY_ID = "memory_status"
MEMORY_FORGET_CAPABILITY_ID = "memory_forget"
REMIND_CAPABILITY_ID = "remind"

TITLES_SPEC = CapabilitySpec(
    capability_id=TITLES_CAPABILITY_ID,
    name="称号一覧",
    description="獲得済みの称号と装備状態を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/titles",
    tags=("titles", "title", "称号", "progression"),
)

TITLE_SET_SPEC = CapabilitySpec(
    capability_id=TITLE_SET_CAPABILITY_ID,
    name="称号変更",
    description="プロフィールに表示する獲得済み称号を変更する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="progression",
    slash_command="/title_set",
    requires_confirmation=True,
    tags=("title", "称号", "profile"),
)

MEMORY_STATUS_SPEC = CapabilitySpec(
    capability_id=MEMORY_STATUS_CAPABILITY_ID,
    name="会話メモリー確認",
    description="保存されているAI会話履歴の件数を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="memory",
    slash_command="/memory",
    tags=("memory", "メモリー", "記憶", "history"),
)

MEMORY_FORGET_SPEC = CapabilitySpec(
    capability_id=MEMORY_FORGET_CAPABILITY_ID,
    name="会話履歴削除",
    description="自分のAI会話履歴を削除する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="memory",
    slash_command="/forget",
    requires_confirmation=True,
    tags=("forget", "memory", "履歴削除", "記憶"),
)

REMIND_SPEC = CapabilitySpec(
    capability_id=REMIND_CAPABILITY_ID,
    name="リマインダー登録",
    description="指定した時間後にメッセージを通知するリマインダーを登録する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="utility",
    slash_command="/remind",
    requires_confirmation=True,
    tags=("remind", "reminder", "リマインダー", "通知"),
)


class UserCapabilityDataSource(Protocol):
    async def evaluate_progress_unlocks(self, guild_id: int, user_id: int):
        ...

    async def get_user_titles(self, guild_id: int, user_id: int):
        ...

    async def has_title(self, guild_id: int, user_id: int, title_key: str) -> bool:
        ...

    async def set_equipped_title(
        self,
        guild_id: int,
        user_id: int,
        title_key: str,
    ) -> None:
        ...

    async def count_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        ...

    async def clear_conversation_history(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
    ) -> int:
        ...

    async def clear_all_user_history(self, guild_id: int, user_id: int) -> int:
        ...

    async def add_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        minutes: int,
    ) -> Any:
        ...


def _require_guild(context: CapabilityContext, capability_id: str) -> int:
    if context.guild_id is None:
        raise ValueError(f"{capability_id} requires guild_id")
    return context.guild_id


def _require_channel(context: CapabilityContext, capability_id: str) -> int:
    if context.channel_id is None:
        raise ValueError(f"{capability_id} requires channel_id")
    return context.channel_id


async def titles_handler(
    data_source: UserCapabilityDataSource,
    context: CapabilityContext,
) -> CapabilityResult:
    guild_id = _require_guild(context, TITLES_CAPABILITY_ID)
    await data_source.evaluate_progress_unlocks(guild_id, context.user_id)
    rows = await data_source.get_user_titles(guild_id, context.user_id)
    return CapabilityResult(TITLES_CAPABILITY_ID, True, value={"rows": rows})


async def title_set_handler(
    data_source: UserCapabilityDataSource,
    context: CapabilityContext,
    *,
    title_key: str,
) -> CapabilityResult:
    guild_id = _require_guild(context, TITLE_SET_CAPABILITY_ID)
    owned = await data_source.has_title(guild_id, context.user_id, title_key)
    if not owned:
        return CapabilityResult(
            TITLE_SET_CAPABILITY_ID,
            False,
            value={"owned": False, "title_key": title_key},
        )

    await data_source.set_equipped_title(guild_id, context.user_id, title_key)
    return CapabilityResult(
        TITLE_SET_CAPABILITY_ID,
        True,
        value={"owned": True, "title_key": title_key},
    )


async def memory_status_handler(
    data_source: UserCapabilityDataSource,
    context: CapabilityContext,
) -> CapabilityResult:
    guild_id = _require_guild(context, MEMORY_STATUS_CAPABILITY_ID)
    channel_id = _require_channel(context, MEMORY_STATUS_CAPABILITY_ID)
    count = await data_source.count_conversation_history(
        guild_id,
        channel_id,
        context.user_id,
    )
    return CapabilityResult(
        MEMORY_STATUS_CAPABILITY_ID,
        True,
        value={"count": count},
    )


async def memory_forget_handler(
    data_source: UserCapabilityDataSource,
    context: CapabilityContext,
    *,
    all_channels: bool,
) -> CapabilityResult:
    guild_id = _require_guild(context, MEMORY_FORGET_CAPABILITY_ID)
    if all_channels:
        deleted = await data_source.clear_all_user_history(
            guild_id,
            context.user_id,
        )
    else:
        channel_id = _require_channel(context, MEMORY_FORGET_CAPABILITY_ID)
        deleted = await data_source.clear_conversation_history(
            guild_id,
            channel_id,
            context.user_id,
        )
    return CapabilityResult(
        MEMORY_FORGET_CAPABILITY_ID,
        True,
        value={"deleted": deleted, "all_channels": all_channels},
    )


async def remind_handler(
    data_source: UserCapabilityDataSource,
    context: CapabilityContext,
    *,
    minutes: int,
    message: str,
) -> CapabilityResult:
    channel_id = _require_channel(context, REMIND_CAPABILITY_ID)
    await data_source.add_reminder(
        context.user_id,
        channel_id,
        message,
        minutes,
    )
    return CapabilityResult(
        REMIND_CAPABILITY_ID,
        True,
        value={"minutes": minutes, "message": message},
    )


def build_user_capability_dispatcher(
    data_source: UserCapabilityDataSource,
) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in (
        TITLES_SPEC,
        TITLE_SET_SPEC,
        MEMORY_STATUS_SPEC,
        MEMORY_FORGET_SPEC,
        REMIND_SPEC,
    ):
        registry.register(spec)

    dispatcher = CapabilityDispatcher(registry)

    async def handle_titles(context, arguments):
        return await titles_handler(data_source, context)

    async def handle_title_set(context, arguments):
        return await title_set_handler(
            data_source,
            context,
            title_key=str(arguments["title_key"]),
        )

    async def handle_memory_status(context, arguments):
        return await memory_status_handler(data_source, context)

    async def handle_memory_forget(context, arguments):
        return await memory_forget_handler(
            data_source,
            context,
            all_channels=bool(arguments["all_channels"]),
        )

    async def handle_remind(context, arguments):
        return await remind_handler(
            data_source,
            context,
            minutes=int(arguments["minutes"]),
            message=str(arguments["message"]),
        )

    dispatcher.register_handler(TITLES_CAPABILITY_ID, handle_titles)
    dispatcher.register_handler(TITLE_SET_CAPABILITY_ID, handle_title_set)
    dispatcher.register_handler(MEMORY_STATUS_CAPABILITY_ID, handle_memory_status)
    dispatcher.register_handler(MEMORY_FORGET_CAPABILITY_ID, handle_memory_forget)
    dispatcher.register_handler(REMIND_CAPABILITY_ID, handle_remind)
    return dispatcher


def _context(*, user_id: int, guild_id: int | None, channel_id: int | None):
    return CapabilityContext(
        user_id=user_id,
        guild_id=guild_id,
        channel_id=channel_id,
    )


async def dispatch_titles(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(TITLES_CAPABILITY_ID),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_title_set(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    title_key: str,
    confirmed: bool,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            TITLE_SET_CAPABILITY_ID,
            {"title_key": title_key},
            confirmed=confirmed,
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_memory_status(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(MEMORY_STATUS_CAPABILITY_ID),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_memory_forget(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int,
    all_channels: bool,
    confirmed: bool,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            MEMORY_FORGET_CAPABILITY_ID,
            {"all_channels": all_channels},
            confirmed=confirmed,
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_remind(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int,
    minutes: int,
    message: str,
    confirmed: bool,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            REMIND_CAPABILITY_ID,
            {"minutes": minutes, "message": message},
            confirmed=confirmed,
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )
