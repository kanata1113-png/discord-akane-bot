from __future__ import annotations

from services.ai_capabilities import DEFINE_SPEC, SUMMARY_SPEC, TRANSLATE_SPEC
from services.community_capabilities import (
    EVENT_CREATE_SPEC,
    MESSAGE_SEARCH_SPEC,
    POLL_CREATE_SPEC,
)
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


MIGRATED_GENERAL_CAPABILITY_SPECS = (
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


# Release E first registers all remaining general-user community capabilities.
# Only MESSAGE_SEARCH is eligible for later direct execution; event/poll retain
# WRITE_CONFIRM semantics and require a dedicated requester-only confirmation UX.
DISCOVERY_RELEASE_E_SPECS = (
    *DISCOVERY_RELEASE_D_SPECS,
    MESSAGE_SEARCH_SPEC,
    EVENT_CREATE_SPEC,
    POLL_CREATE_SPEC,
)


def migrated_general_specs():
    return MIGRATED_GENERAL_CAPABILITY_SPECS


def discovery_pilot_specs():
    return DISCOVERY_PILOT_SPECS


def discovery_release_c_specs():
    return DISCOVERY_RELEASE_C_SPECS


def discovery_release_d_specs():
    return DISCOVERY_RELEASE_D_SPECS


def discovery_release_e_specs():
    return DISCOVERY_RELEASE_E_SPECS
