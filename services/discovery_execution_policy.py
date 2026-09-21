from __future__ import annotations

from services.progression_capabilities import (
    ACHIEVEMENTS_CAPABILITY_ID,
    LEADERBOARD_CAPABILITY_ID,
    LEVEL_CAPABILITY_ID,
    PROFILE_CAPABILITY_ID,
    WEEKLY_CAPABILITY_ID,
)
from services.user_capabilities import MEMORY_STATUS_CAPABILITY_ID


DIRECT_EXECUTION_CAPABILITY_IDS = frozenset(
    {
        LEVEL_CAPABILITY_ID,
        LEADERBOARD_CAPABILITY_ID,
        WEEKLY_CAPABILITY_ID,
        PROFILE_CAPABILITY_ID,
        ACHIEVEMENTS_CAPABILITY_ID,
        MEMORY_STATUS_CAPABILITY_ID,
    }
)


def can_direct_execute_discovery_capability(capability_id: str) -> bool:
    """Return True only for explicitly approved direct-execution capabilities.

    Every allowlisted capability is argument-free at selection time and is
    treated as safe for direct execution after explicit requester selection.
    ``rankings`` requires a category, ``fortune`` persists first-read state,
    ``titles`` performs unlock bookkeeping, AI tools require arguments and can
    incur external cost, and write/moderation/admin capabilities remain excluded.
    """

    return capability_id in DIRECT_EXECUTION_CAPABILITY_IDS
