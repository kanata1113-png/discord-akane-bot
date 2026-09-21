from __future__ import annotations

import hashlib
import random

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
LEADERBOARD_CAPABILITY_ID = "leaderboard"
WEEKLY_CAPABILITY_ID = "weekly"
RANKINGS_CAPABILITY_ID = "rankings"
PROFILE_CAPABILITY_ID = "profile"
ACHIEVEMENTS_CAPABILITY_ID = "achievements"
FORTUNE_CAPABILITY_ID = "fortune"

LEVEL_SPEC = CapabilitySpec(
    capability_id=LEVEL_CAPABILITY_ID,
    name="レベル確認",
    description="自分の現在レベルとXP進捗を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/level",
    tags=("level", "xp", "progression"),
)

LEADERBOARD_SPEC = CapabilitySpec(
    capability_id=LEADERBOARD_CAPABILITY_ID,
    name="レベルランキング",
    description="全体のレベル・XPランキングTOP30を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/leaderboard",
    tags=("leaderboard", "level", "xp", "ranking"),
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

PROFILE_SPEC = CapabilitySpec(
    capability_id=PROFILE_CAPABILITY_ID,
    name="プロフィール",
    description="サーバー内のプロフィールと進行状況を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/profile",
    tags=("profile", "level", "xp", "achievements", "titles"),
)

ACHIEVEMENTS_SPEC = CapabilitySpec(
    capability_id=ACHIEVEMENTS_CAPABILITY_ID,
    name="実績一覧",
    description="サーバー内の実績解除状況を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/achievements",
    tags=("achievements", "progression", "profile"),
)

FORTUNE_SPEC = CapabilitySpec(
    capability_id=FORTUNE_CAPABILITY_ID,
    name="今日の運勢",
    description="今日の運勢を生成または確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/fortune",
    tags=("fortune", "daily", "progression"),
)


class ProgressionDataSource(Protocol):
    async def get_level_info(self, user_id: int) -> dict[str, Any]:
        ...

    async def get_leaderboard(self, limit: int):
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
    async def evaluate_progress_unlocks(self, guild_id: int, user_id: int):
        ...

    async def get_user_stats(self, guild_id: int, user_id: int):
        ...

    async def get_user_achievements(self, guild_id: int, user_id: int):
        ...

    async def get_user_titles(self, guild_id: int, user_id: int):
        ...

    async def get_equipped_title(self, guild_id: int, user_id: int):
        ...

    async def get_today_fortune(self, guild_id: int, user_id: int):
        ...

    async def save_today_fortune(
        self, guild_id: int, user_id: int, fortune_key: str, score: int
    ):
        ...

    async def increment_fortune_count(self, guild_id: int, user_id: int):
        ...



async def level_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
) -> CapabilityResult:
    info = await data_source.get_level_info(context.user_id)
    return CapabilityResult(LEVEL_CAPABILITY_ID, True, value=info)


async def leaderboard_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    limit: int,
) -> CapabilityResult:
    rows = await data_source.get_leaderboard(limit)
    return CapabilityResult(
        LEADERBOARD_CAPABILITY_ID,
        True,
        value={"rows": rows},
    )


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


async def profile_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    target_user_id: int,
) -> CapabilityResult:
    if context.guild_id is None:
        raise ValueError("profile requires guild_id")

    await data_source.evaluate_progress_unlocks(context.guild_id, target_user_id)
    level_info = await data_source.get_level_info(target_user_id)
    stats = await data_source.get_user_stats(context.guild_id, target_user_id)
    achievements = await data_source.get_user_achievements(
        context.guild_id, target_user_id
    )
    titles = await data_source.get_user_titles(context.guild_id, target_user_id)
    equipped_key = await data_source.get_equipped_title(
        context.guild_id, target_user_id
    )
    weekly_xp = await data_source.get_user_weekly_xp(
        context.guild_id, target_user_id
    )
    weekly_rank = await data_source.get_weekly_rank(
        context.guild_id, target_user_id
    )

    return CapabilityResult(
        PROFILE_CAPABILITY_ID,
        True,
        value={
            "level_info": level_info,
            "stats": stats,
            "achievements": achievements,
            "titles": titles,
            "equipped_key": equipped_key,
            "weekly_xp": weekly_xp,
            "weekly_rank": weekly_rank,
        },
    )


async def achievements_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    target_user_id: int,
) -> CapabilityResult:
    if context.guild_id is None:
        raise ValueError("achievements requires guild_id")

    await data_source.evaluate_progress_unlocks(context.guild_id, target_user_id)
    rows = await data_source.get_user_achievements(
        context.guild_id, target_user_id
    )
    return CapabilityResult(
        ACHIEVEMENTS_CAPABILITY_ID,
        True,
        value={"rows": rows},
    )


async def fortune_handler(
    data_source: ProgressionDataSource,
    context: CapabilityContext,
    *,
    today: str,
) -> CapabilityResult:
    if context.guild_id is None:
        raise ValueError("fortune requires guild_id")

    existing = await data_source.get_today_fortune(
        context.guild_id, context.user_id
    )
    is_new = existing is None

    if existing:
        fortune_key = existing[0]
        score = int(existing[1])
    else:
        seed_text = (
            f"{context.guild_id}:"
            f"{context.user_id}:"
            f"{today}:"
            "akane-v33"
        )
        digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
        rng = random.Random(int(digest[:16], 16))
        score = rng.randint(1, 100)

        if score >= 96:
            fortune_key = "super_lucky"
        elif score >= 81:
            fortune_key = "great_lucky"
        elif score >= 61:
            fortune_key = "lucky"
        elif score >= 41:
            fortune_key = "small_lucky"
        elif score >= 21:
            fortune_key = "neutral"
        else:
            fortune_key = "careful"

        await data_source.save_today_fortune(
            context.guild_id,
            context.user_id,
            fortune_key,
            score,
        )
        await data_source.increment_fortune_count(
            context.guild_id,
            context.user_id,
        )

    return CapabilityResult(
        FORTUNE_CAPABILITY_ID,
        True,
        value={
            "fortune_key": fortune_key,
            "score": score,
            "is_new": is_new,
        },
    )


def build_progression_pilot_dispatcher(
    data_source: ProgressionDataSource,
) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in (
        LEVEL_SPEC,
        LEADERBOARD_SPEC,
        WEEKLY_SPEC,
        RANKINGS_SPEC,
        PROFILE_SPEC,
        ACHIEVEMENTS_SPEC,
        FORTUNE_SPEC,
    ):
        registry.register(spec)

    dispatcher = CapabilityDispatcher(registry)

    async def handle_level(context, arguments):
        return await level_handler(data_source, context)

    async def handle_leaderboard(context, arguments):
        return await leaderboard_handler(
            data_source,
            context,
            limit=int(arguments["limit"]),
        )

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
    dispatcher.register_handler(LEADERBOARD_CAPABILITY_ID, handle_leaderboard)
    dispatcher.register_handler(WEEKLY_CAPABILITY_ID, handle_weekly)
    async def handle_profile(context, arguments):
        return await profile_handler(
            data_source,
            context,
            target_user_id=int(arguments["target_user_id"]),
        )

    async def handle_achievements(context, arguments):
        return await achievements_handler(
            data_source,
            context,
            target_user_id=int(arguments["target_user_id"]),
        )

    dispatcher.register_handler(RANKINGS_CAPABILITY_ID, handle_rankings)
    dispatcher.register_handler(PROFILE_CAPABILITY_ID, handle_profile)
    async def handle_fortune(context, arguments):
        return await fortune_handler(
            data_source,
            context,
            today=str(arguments["today"]),
        )

    dispatcher.register_handler(ACHIEVEMENTS_CAPABILITY_ID, handle_achievements)
    dispatcher.register_handler(FORTUNE_CAPABILITY_ID, handle_fortune)
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


async def dispatch_leaderboard(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
    limit: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(LEADERBOARD_CAPABILITY_ID, {"limit": limit}),
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


async def dispatch_profile(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    target_user_id: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(PROFILE_CAPABILITY_ID, {"target_user_id": target_user_id}),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_achievements(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    target_user_id: int,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(
            ACHIEVEMENTS_CAPABILITY_ID,
            {"target_user_id": target_user_id},
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )


async def dispatch_fortune(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    today: str,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(FORTUNE_CAPABILITY_ID, {"today": today}),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id),
    )
