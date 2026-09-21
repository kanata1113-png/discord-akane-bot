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

LEVEL_SPEC = CapabilitySpec(
    capability_id=LEVEL_CAPABILITY_ID,
    name="レベル確認",
    description="自分の現在レベルとXP進捗を確認する",
    risk=CapabilityRisk.READ_ONLY,
    category="progression",
    slash_command="/level",
    tags=("level", "xp", "progression"),
)


class LevelDataSource(Protocol):
    async def get_level_info(self, user_id: int) -> dict[str, Any]:
        ...


async def level_handler(
    data_source: LevelDataSource,
    context: CapabilityContext,
) -> CapabilityResult:
    """Return the existing level-info payload without Discord presentation."""

    info = await data_source.get_level_info(context.user_id)
    return CapabilityResult(
        capability_id=LEVEL_CAPABILITY_ID,
        ok=True,
        value=info,
    )


def build_progression_pilot_dispatcher(
    data_source: LevelDataSource,
) -> CapabilityDispatcher:
    """Build the B1 pilot runtime.

    B1 deliberately registers only /level. More progression capabilities are
    added after the shared-handler seam is verified.
    """

    registry = CapabilityRegistry()
    registry.register(LEVEL_SPEC)
    dispatcher = CapabilityDispatcher(registry)

    async def handle_level(context, arguments):
        return await level_handler(data_source, context)

    dispatcher.register_handler(LEVEL_CAPABILITY_ID, handle_level)
    return dispatcher


async def dispatch_level(
    dispatcher: CapabilityDispatcher,
    *,
    user_id: int,
    guild_id: int | None,
    channel_id: int | None,
) -> CapabilityResult:
    return await dispatcher.dispatch(
        CapabilityRequest(LEVEL_CAPABILITY_ID),
        CapabilityContext(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
        ),
    )
