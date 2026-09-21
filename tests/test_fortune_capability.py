import hashlib
import random

import pytest

from services.progression_capabilities import (
    FORTUNE_SPEC,
    build_progression_pilot_dispatcher,
    dispatch_fortune,
)


class FakeFortuneDataSource:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    async def get_level_info(self, user_id):
        return {}

    async def get_weekly_xp_leaderboard(self, guild_id, limit):
        return []

    def current_week_key(self):
        return "2026-W39"

    async def get_user_weekly_xp(self, guild_id, user_id):
        return 0

    async def get_weekly_rank(self, guild_id, user_id):
        return None

    async def get_message_leaderboard(self, guild_id, limit):
        return []

    async def get_ai_leaderboard(self, guild_id, limit):
        return []

    async def get_achievement_leaderboard(self, guild_id, limit):
        return []

    async def evaluate_progress_unlocks(self, guild_id, user_id):
        return {}

    async def get_user_stats(self, guild_id, user_id):
        return {}

    async def get_user_achievements(self, guild_id, user_id):
        return []

    async def get_user_titles(self, guild_id, user_id):
        return []

    async def get_equipped_title(self, guild_id, user_id):
        return None

    async def get_today_fortune(self, guild_id, user_id):
        self.calls.append(("get", guild_id, user_id))
        return self.existing

    async def save_today_fortune(
        self, guild_id, user_id, fortune_key, score
    ):
        self.calls.append(("save", guild_id, user_id, fortune_key, score))

    async def increment_fortune_count(self, guild_id, user_id):
        self.calls.append(("increment", guild_id, user_id))
        return 1


def legacy_expected(guild_id, user_id, today):
    seed = f"{guild_id}:{user_id}:{today}:akane-v33"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    score = random.Random(int(digest[:16], 16)).randint(1, 100)
    if score >= 96:
        key = "super_lucky"
    elif score >= 81:
        key = "great_lucky"
    elif score >= 61:
        key = "lucky"
    elif score >= 41:
        key = "small_lucky"
    elif score >= 21:
        key = "neutral"
    else:
        key = "careful"
    return key, score


def test_fortune_metadata_keeps_existing_user_policy():
    assert FORTUNE_SPEC.slash_command == "/fortune"
    assert FORTUNE_SPEC.requires_confirmation is False


@pytest.mark.asyncio
async def test_existing_daily_fortune_is_read_without_mutation():
    source = FakeFortuneDataSource(existing=("lucky", 77))
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_fortune(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        today="2026-09-21",
    )

    assert result.value == {
        "fortune_key": "lucky",
        "score": 77,
        "is_new": False,
    }
    assert source.calls == [("get", 456, 20)]


@pytest.mark.asyncio
async def test_first_daily_fortune_preserves_seed_and_write_order():
    source = FakeFortuneDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)
    expected_key, expected_score = legacy_expected(
        456, 20, "2026-09-21"
    )

    result = await dispatch_fortune(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        today="2026-09-21",
    )

    assert result.value == {
        "fortune_key": expected_key,
        "score": expected_score,
        "is_new": True,
    }
    assert source.calls == [
        ("get", 456, 20),
        ("save", 456, 20, expected_key, expected_score),
        ("increment", 456, 20),
    ]
