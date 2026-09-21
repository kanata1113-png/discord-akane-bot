from __future__ import annotations

from services.progression_capabilities import (
    ACHIEVEMENTS_CAPABILITY_ID,
    LEADERBOARD_CAPABILITY_ID,
    LEVEL_CAPABILITY_ID,
    PROFILE_CAPABILITY_ID,
    WEEKLY_CAPABILITY_ID,
)


DIRECT_EXECUTION_CAPABILITY_IDS = frozenset(
    {
        LEVEL_CAPABILITY_ID,
        LEADERBOARD_CAPABILITY_ID,
        WEEKLY_CAPABILITY_ID,
        PROFILE_CAPABILITY_ID,
        ACHIEVEMENTS_CAPABILITY_ID,
    }
)


def can_direct_execute_discovery_capability(capability_id: str) -> bool:
    """Return True only for explicitly approved direct-execution capabilities.

    ``rankings`` remains selection-only because it requires an additional
    category argument. ``fortune`` remains selection-only because first access
    persists state. Unknown, moderation, and admin capabilities fail closed.
    """

    return capability_id in DIRECT_EXECUTION_CAPABILITY_IDS
