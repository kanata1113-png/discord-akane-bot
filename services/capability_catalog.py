from __future__ import annotations

from services.ai_capabilities import DEFINE_SPEC, SUMMARY_SPEC, TRANSLATE_SPEC
from services.progression_capabilities import (
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
    LEADERBOARD_SPEC,
    LEVEL_SPEC,
    PROFILE_SPEC,
    RANKINGS_SPEC,
    WEEKLY_SPEC,
)
from services.user_capabilities import (
    MEMORY_FORGET_SPEC,
    MEMORY_STATUS_SPEC,
    REMIND_SPEC,
    TITLES_SPEC,
    TITLE_SET_SPEC,
)


# Capabilities already represented by an executable CapabilitySpec in Release C.
MIGRATED_GENERAL_CAPABILITY_SPECS = (
    TRANSLATE_SPEC,
    DEFINE_SPEC,
    SUMMARY_SPEC,
    LEVEL_SPEC,
    LEADERBOARD_SPEC,
    REMIND_SPEC,
    MEMORY_STATUS_SPEC,
    MEMORY_FORGET_SPEC,
    PROFILE_SPEC,
    FORTUNE_SPEC,
    ACHIEVEMENTS_SPEC,
    TITLES_SPEC,
    TITLE_SET_SPEC,
    WEEKLY_SPEC,
    RANKINGS_SPEC,
)


# Preserve the exact B2 discovery surface until a dedicated expansion gate lands.
DISCOVERY_PILOT_SPECS = (
    LEVEL_SPEC,
    WEEKLY_SPEC,
    RANKINGS_SPEC,
    PROFILE_SPEC,
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
)


def migrated_general_specs():
    """Return the immutable Release C migrated general capability catalog."""

    return MIGRATED_GENERAL_CAPABILITY_SPECS


def discovery_pilot_specs():
    """Return the currently approved natural-language discovery surface."""

    return DISCOVERY_PILOT_SPECS
