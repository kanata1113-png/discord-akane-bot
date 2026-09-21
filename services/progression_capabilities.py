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


LEVEL_CAPABILITY_ID = "level"
WEEKLY_CAPABILITY_ID = "weekly"
RANKINGS_CAPABILITY_ID = "rankings"

LEVEL_SPEC = CapabilitySpec(
    capability_id=LEVEL_CAPABILITY_ID,
    name="レベル確認",
    description="自分の現在レベルとXP進捗を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/level",
    tags=("level", "xp", "progression"),
)

WEEKLY_SPEC = CapabilitySpec(
    capability_id=WEEKLY_CAPABILITY_ID,
    name="今週のXPランキング",
    description="サーバー内の週間XP順位と自分の順位を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/weekly",
    tags=("weekly", "xp", "ranking"),
)

RANKINGS_SPEC = CapabilitySpec(
    capability_id=RANKINGS_CAPABILITY_ID,
    name="サーバー内ランキング",
    description="週間XP・発言・AI会話・実績のランキングを確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/rankings",
    tags=("ranking", "weekly", "messages", "ai", "achievements"),
)


class ProgressionDataSource(Protocol):
    async def get_level_info(self, user_id: int) -> dict[str, Any]:
        ...

    async def get_weekly_xp_leaderboard(self, guild_id: int, limit: int):
        ...

    def current_week_key(self) -> str:
        ...

    async def get_user_weekly_xp(self, guild_id: int, user_id: int):
        ...

    async def get_weekly_rank(self, guild_id: int, user_id: int):
        ...

    async def get_message_leaderboard(self, guild_id: int, limit: int):
        ...

    async def get_ai_leaderboard(self, guild_id: int, limit: int):
        ...

    async def get_achievement_leaderboard(self, guild_id: int, limit: int):
        ...


async def level_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
) -> CapabilityResult:
    info = await data_source.get_level_info(context.user_id)
    return CapabilityResult(LEVEL_CAPABILITY_ID, True, value=info)


async def weekly_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    limit: int,
) -> CapabilityResult:
    if context.guild_id is None:
        raise ValueError("weekly requires guild_id")

    rows = await data_source.get_weekly_xp_leaderboard(
        context.guild_id,
        limit,
    )
    week_key = data_source.current_week_key()
    user_xp = await data_source.get_user_weekly_xp(
        context.guild_id,
        context.user_id,
    )
    user_rank = await data_source.get_weekly_rank(
        context.guild_id,
        context.user_id,
    )
    return CapabilityResult(
        WEEKLY_CAPABILITY_ID,
        True,
        value={
            "rows": rows,
            "week_key": week_key,
            "user_xp": user_xp,
            "user_rank": user_rank,
        },
    )


async def rankings_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    category: str,
    limit: int,
) -> CapabilityResult:
    if context.guild_id is None:
        raise ValueError("rankings requires guild_id")

    if category == "weekly":
        rows = await data_source.get_weekly_xp_leaderboard(context.guild_id, limit)
        title, suffix = "🔥 週間XPランキング", "XP"
    elif category == "messages":
        rows = await data_source.get_message_leaderboard(context.guild_id, limit)
        title, suffix = "💬 発言数ランキング", "発言"
    elif category == "ai":
        rows = await data_source.get_ai_leaderboard(context.guild_id, limit)
        title, suffix = "🤖 AI会話ランキング", "回"
    elif category == "achievements":
        rows = await data_source.get_achievement_leaderboard(context.guild_id, limit)
        title, suffix = "🏆 実績ランキング", "個"
    else:
        raise ValueError(f"unsupported rankings category: {category}")

    return CapabilityResult(
        RANKINGS_CAPABILITY_ID,
        True,
        value={"rows": rows, "title": title, "suffix": suffix},
    )


def build_progression_pilot_dispatcher(
    data_source: ProgressionDataSource,
) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in (LEVEL_SPEC, WEEKLY_SPEC, RANKINGS_SPEC):
        registry.register(spec)

    dispatcher = CapabilityDispatcher(registry)

    async def handle_level(context, arguments):
        return await level_handler(data_source, context)

    async def handle_weekly(context, arguments):
        return await weekly_handler(
            data_source,
            context,
            limit=int(arguments["limit"]),
        )

    async def handle_rankings(context, arguments):
        return await rankings_handler(
            data_source,
            context,
            category=str(arguments["category"]),
            limit=int(arguments["limit"]),
        )

    dispatcher.register_handler(LEVEL_CAPABILITY_ID, handle_level)
    dispatcher.register_handler(WEEKLY_CAPABILITY_ID, handle_weekly)
    dispatcher.register_handler(RANKINGS_CAPABILITY_ID, handle_rankings)
    return dispatcher


def _context(*, user_id: int, guild_id: int | None, channel_id: int | None):
    return CapabilityContext(
        user_id=user_id,
        guild_id=guild_id,
        channel_id=channel_id,
    )


async def dispatch_level(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(LEVEL_CAPABILITY_ID),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_weekly(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    limit: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(WEEKLY_CAPABILITY_ID, {"limit": limit}),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_rankings(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    category: str,
    limit: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            RANKINGS_CAPABILITY_ID,
            {"category": category, "limit": limit},
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )
