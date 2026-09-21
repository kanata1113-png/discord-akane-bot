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


KICK_CAPABILITY_ID = "moderation_kick"
BAN_CAPABILITY_ID = "moderation_ban"
PURGE_CAPABILITY_ID = "moderation_purge"

KICK_SPEC = CapabilitySpec(
    capability_id=KICK_CAPABILITY_ID,
    name="メンバーKick",
    description="管理者が指定メンバーをサーバーからKickする",
    risk=CapabilityRisk.MODERATION,
    category="moderation",
    slash_command="/admin kick",
    requires_confirmation=True,
    discoverable=False,
    tags=("admin", "moderation", "kick"),
)

BAN_SPEC = CapabilitySpec(
    capability_id=BAN_CAPABILITY_ID,
    name="メンバーBan",
    description="管理者が指定メンバーをサーバーからBanする",
    risk=CapabilityRisk.MODERATION,
    category="moderation",
    slash_command="/admin ban",
    requires_confirmation=True,
    discoverable=False,
    tags=("admin", "moderation", "ban"),
)

PURGE_SPEC = CapabilitySpec(
    capability_id=PURGE_CAPABILITY_ID,
    name="メッセージ削除",
    description="管理者がチャンネル内メッセージを一括削除する",
    risk=CapabilityRisk.MODERATION,
    category="moderation",
    slash_command="/admin purge",
    requires_confirmation=True,
    discoverable=False,
    tags=("admin", "moderation", "purge"),
)

MODERATION_CAPABILITY_SPECS = (KICK_SPEC, BAN_SPEC, PURGE_SPEC)


class ModerationDataSource(Protocol):
    async def kick_member(self, *, context: CapabilityContext, target_user_id: int) -> dict[str, Any]: ...
    async def ban_member(self, *, context: CapabilityContext, target_user_id: int) -> dict[str, Any]: ...
    async def purge_messages(
        self,
        *,
        context: CapabilityContext,
        amount: int,
        target_user_id: int | None,
        hours: int | None,
    ) -> dict[str, Any]: ...


def _context(*, user_id: int, guild_id: int | None, channel_id: int | None, interaction=None) -> CapabilityContext:
    return CapabilityContext(
        user_id=user_id,
        guild_id=guild_id,
        channel_id=channel_id,
        interaction=interaction,
    )


def build_moderation_capability_dispatcher(data_source: ModerationDataSource) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    for spec in MODERATION_CAPABILITY_SPECS:
        registry.register(spec)
    dispatcher = CapabilityDispatcher(registry)

    async def handle_kick(context, arguments):
        value = await data_source.kick_member(
            context=context,
            target_user_id=int(arguments["target_user_id"]),
        )
        return CapabilityResult(KICK_CAPABILITY_ID, True, value=value)

    async def handle_ban(context, arguments):
        value = await data_source.ban_member(
            context=context,
            target_user_id=int(arguments["target_user_id"]),
        )
        return CapabilityResult(BAN_CAPABILITY_ID, True, value=value)

    async def handle_purge(context, arguments):
        target = arguments.get("target_user_id")
        value = await data_source.purge_messages(
            context=context,
            amount=int(arguments["amount"]),
            target_user_id=int(target) if target is not None else None,
            hours=int(arguments["hours"]) if arguments.get("hours") is not None else None,
        )
        return CapabilityResult(PURGE_CAPABILITY_ID, True, value=value)

    dispatcher.register_handler(KICK_CAPABILITY_ID, handle_kick)
    dispatcher.register_handler(BAN_CAPABILITY_ID, handle_ban)
    dispatcher.register_handler(PURGE_CAPABILITY_ID, handle_purge)
    return dispatcher


async def dispatch_kick(dispatcher: CapabilityDispatcher, *, user_id: int, guild_id: int, channel_id: int | None, target_user_id: int, confirmed: bool, interaction=None):
    return await dispatcher.dispatch(
        CapabilityRequest(KICK_CAPABILITY_ID, {"target_user_id": target_user_id}, confirmed=confirmed),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )


async def dispatch_ban(dispatcher: CapabilityDispatcher, *, user_id: int, guild_id: int, channel_id: int | None, target_user_id: int, confirmed: bool, interaction=None):
    return await dispatcher.dispatch(
        CapabilityRequest(BAN_CAPABILITY_ID, {"target_user_id": target_user_id}, confirmed=confirmed),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )


async def dispatch_purge(dispatcher: CapabilityDispatcher, *, user_id: int, guild_id: int, channel_id: int | None, amount: int, target_user_id: int | None, hours: int | None, confirmed: bool, interaction=None):
    return await dispatcher.dispatch(
        CapabilityRequest(
            PURGE_CAPABILITY_ID,
            {"amount": amount, "target_user_id": target_user_id, "hours": hours},
            confirmed=confirmed,
        ),
        _context(user_id=user_id, guild_id=guild_id, channel_id=channel_id, interaction=interaction),
    )
