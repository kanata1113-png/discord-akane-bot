from __future__ import annotations

import logging
from typing import Protocol

import discord

from services.discovery_execution_policy import (
    can_direct_execute_discovery_capability,
)


logger = logging.getLogger("AkaneBot")


class DiscoverySelection(Protocol):
    capability_id: str


async def execute_discovery_selection(
    interaction: discord.Interaction,
    selection: DiscoverySelection,
) -> bool:
    """Execute an explicitly selected, approved B2 capability.

    The existing GeneralCog slash-command callbacks remain the sole Discord
    presentation adapters. They already dispatch through the progression
    CapabilityDispatcher, so this path adds a new explicit-selection entry
    point without duplicating domain logic or changing persistence semantics.

    Returns False for every capability outside the approved pilot. That keeps
    rankings (missing required category), fortune (first-read persistence),
    unknown, moderation, and admin capabilities fail-closed.
    """

    capability_id = selection.capability_id
    if not can_direct_execute_discovery_capability(capability_id):
        return False

    general_cog = interaction.client.get_cog("GeneralCog")
    if general_cog is None:
        logger.error(
            "Discovery direct execution unavailable | GeneralCog missing | "
            f"capability={capability_id}"
        )
        return False

    command = getattr(general_cog, capability_id, None)
    callback = getattr(command, "callback", None)
    if callback is None:
        logger.error(
            "Discovery direct execution unavailable | callback missing | "
            f"capability={capability_id}"
        )
        return False

    logger.info(
        "Discovery direct execution | "
        f"user={interaction.user.id} | capability={capability_id}"
    )

    if capability_id in {"profile", "achievements"}:
        await callback(general_cog, interaction, None)
    else:
        await callback(general_cog, interaction)

    return True
