from __future__ import annotations

from typing import Any, Mapping, Protocol

from services.capability_core import (
    CapabilityContext,
    CapabilityDispatcher,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityRisk,
    CapabilitySpec,
)


def _spec(capability_id: str, name: str, slash_command: str, *tags: str) -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=capability_id,
        name=name,
        description=name,
        risk=CapabilityRisk.ADMIN,
        category="admin",
        slash_command=slash_command,
        requires_confirmation=True,
        discoverable=False,
        tags=("admin", *tags),
    )


CONFIG_LOG_SPEC = _spec("admin_config_log", "監査ログ設定", "/admin config_log", "config")
CONFIG_WELCOME_SPEC = _spec("admin_config_welcome", "挨拶設定", "/admin config_welcome", "config")
CONFIG_STARBOARD_SPEC = _spec("admin_config_starboard", "殿堂入り設定", "/admin config_starboard", "config")
CONFIG_AUTOCHAT_SPEC = _spec("admin_config_autochat", "常駐チャット設定", "/admin config_autochat", "config")
CONFIG_MONTHLY_SPEC = _spec("admin_config_monthly", "月次ルール通知設定", "/admin config_monthly", "config")
SETUP_TICKET_SPEC = _spec("admin_setup_ticket", "Ticketパネル設置", "/admin setup_ticket", "ticket")
ROLEPANEL_SPEC = _spec("admin_rolepanel", "リアクションロール設定", "/admin rolepanel", "role")
LEVEL_REWARD_SPEC = _spec("admin_level_reward", "レベル報酬設定", "/admin level_reward", "level")
LEVEL_REWARD_REMOVE_SPEC = _spec("admin_level_reward_remove", "レベル報酬削除", "/admin level_reward_remove", "level")
FILTER_ADD_SPEC = _spec("admin_filter_add", "NGワード追加", "/admin filter_add", "filter")
RESPONSE_ADD_SPEC = _spec("admin_response_add", "自動応答追加", "/admin response_add", "response")

ADMIN_WRITE_CAPABILITY_SPECS = (
    CONFIG_LOG_SPEC,
    CONFIG_WELCOME_SPEC,
    CONFIG_STARBOARD_SPEC,
    CONFIG_AUTOCHAT_SPEC,
    CONFIG_MONTHLY_SPEC,
    SETUP_TICKET_SPEC,
    ROLEPANEL_SPEC,
    LEVEL_REWARD_SPEC,
    LEVEL_REWARD_REMOVE_SPEC,
    FILTER_ADD_SPEC,
    RESPONSE_ADD_SPEC,
)


class AdminDataSource(Protocol):
    async def perform_admin_action(
        self,
        *,
        context: CapabilityContext,
        capability_id: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]: ...


def build_admin_capability_dispatcher(data_source: AdminDataSource) -> CapabilityDispatcher:
    registry = CapabilityRegistry()
    dispatcher = CapabilityDispatcher(registry)
    for spec in ADMIN_WRITE_CAPABILITY_SPECS:
        registry.register(spec)

        async def handler(context, arguments, *, capability_id=spec.capability_id):
            value = await data_source.perform_admin_action(
                context=context,
                capability_id=capability_id,
                arguments=arguments,
            )
            return CapabilityResult(capability_id, True, value=value)

        dispatcher.register_handler(spec.capability_id, handler)
    return dispatcher


async def dispatch_admin_action(
    dispatcher: CapabilityDispatcher,
    *,
    capability_id: str,
    user_id: int,
    guild_id: int,
    channel_id: int | None,
    arguments: Mapping[str, Any],
    confirmed: bool,
    interaction=None,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(capability_id, arguments, confirmed=confirmed),
        CapabilityContext(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            interaction=interaction,
        ),
    )
