from __future__ import annotations

from services.ai_capabilities import DEFINE_SPEC, SUMMARY_SPEC, TRANSLATE_SPEC
from services.community_capabilities import EVENT_CREATE_SPEC, MESSAGE_SEARCH_SPEC, POLL_CREATE_SPEC
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


# Canonical v4 general-user capability catalog.
GENERAL_CAPABILITY_SPECS = (
    TRANSLATE_SPEC,
    DEFINE_SPEC,
    SUMMARY_SPEC,
    EVENT_CREATE_SPEC,
    POLL_CREATE_SPEC,
    MESSAGE_SEARCH_SPEC,
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

# Canonical natural-language discovery surface. All general-user capabilities
# are represented; execution policy remains separate and risk-aware.
DISCOVERY_SPECS = GENERAL_CAPABILITY_SPECS

# Historical aliases retained for regression compatibility during Release G.
MIGRATED_GENERAL_CAPABILITY_SPECS = GENERAL_CAPABILITY_SPECS
DISCOVERY_PILOT_SPECS = (
    LEVEL_SPEC,
    WEEKLY_SPEC,
    RANKINGS_SPEC,
    PROFILE_SPEC,
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
)
DISCOVERY_RELEASE_C_SPECS = (
    *DISCOVERY_PILOT_SPECS,
    LEADERBOARD_SPEC,
    TITLES_SPEC,
    MEMORY_STATUS_SPEC,
    TRANSLATE_SPEC,
    DEFINE_SPEC,
    SUMMARY_SPEC,
)
DISCOVERY_RELEASE_D_SPECS = (
    *DISCOVERY_RELEASE_C_SPECS,
    TITLE_SET_SPEC,
    MEMORY_FORGET_SPEC,
    REMIND_SPEC,
)
DISCOVERY_RELEASE_E_SPECS = DISCOVERY_SPECS


def general_capability_specs():
    return GENERAL_CAPABILITY_SPECS


def discovery_specs():
    return DISCOVERY_SPECS


def migrated_general_specs():
    return GENERAL_CAPABILITY_SPECS


def discovery_pilot_specs():
    return DISCOVERY_PILOT_SPECS


def discovery_release_c_specs():
    return DISCOVERY_RELEASE_C_SPECS


def discovery_release_d_specs():
    return DISCOVERY_RELEASE_D_SPECS


def discovery_release_e_specs():
    return DISCOVERY_SPECS
