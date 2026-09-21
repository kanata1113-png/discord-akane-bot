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


# Release D adds only the three migrated WRITE_CONFIRM capabilities that have a
# dedicated requester-only argument/scope + final-confirmation UI. Their presence
# in discovery does not put them in the direct-execution allowlist.
DISCOVERY_RELEASE_D_SPECS = (
    *DISCOVERY_RELEASE_C_SPECS,
    TITLE_SET_SPEC,
    MEMORY_FORGET_SPEC,
    REMIND_SPEC,
)


def migrated_general_specs():
    return MIGRATED_GENERAL_CAPABILITY_SPECS


def discovery_pilot_specs():
    return DISCOVERY_PILOT_SPECS


def discovery_release_c_specs():
    return DISCOVERY_RELEASE_C_SPECS


def discovery_release_d_specs():
    return DISCOVERY_RELEASE_D_SPECS
