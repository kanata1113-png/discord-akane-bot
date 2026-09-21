from __future__ import annotations

import discord

from services.capability_discovery import DiscoveryCandidate


DIRECT_READ_ONLY_CAPABILITY_IDS = frozenset(
    {
        "level",
        "weekly",
        "profile",
        "achievements",
    }
)


async def execute_selected_read_only(
    interaction: discord.Interaction,
    candidate: DiscoveryCandidate,
) -> bool:
    """Execute only explicitly selected, argument-complete read capabilities.

    Returns True when the selected capability was handed to its established
    Discord command callback. Unsupported candidates are intentionally left for
    slash-command guidance by the Candidate Panel.

    `rankings` is excluded because discovery does not yet carry its required
    category argument. `fortune` is excluded because first access persists
    daily state and progression bookkeeping.
    """

    capability_id = candidate.capability_id
    if capability_id not in DIRECT_READ_ONLY_CAPABILITY_IDS:
        return False

    client = interaction.client
    general_cog = client.get_cog("GeneralCog")
    if general_cog is None:
        return False

    command = getattr(general_cog, capability_id, None)
    callback = getattr(command, "callback", None)
    if callback is None:
        return False

    await callback(general_cog, interaction)
    return True
