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


COMMAND_ATTRIBUTE_BY_CAPABILITY_ID = {
    "memory_status": "memory",
}


async def execute_discovery_selection(
    interaction: discord.Interaction,
    selection: DiscoverySelection,
) -> bool:
    """Execute an explicitly selected, approved discovery capability.

    Existing GeneralCog slash-command callbacks remain the Discord presentation
    adapters. Capability IDs normally match command attribute names; explicit
    aliases cover intentionally different runtime IDs such as memory_status.
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

    command_name = COMMAND_ATTRIBUTE_BY_CAPABILITY_ID.get(
        capability_id,
        capability_id,
    )
    command = getattr(general_cog, command_name, None)
    callback = getattr(command, "callback", None)
    if callback is None:
        logger.error(
            "Discovery direct execution unavailable | callback missing | "
            f"capability={capability_id} | command={command_name}"
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
