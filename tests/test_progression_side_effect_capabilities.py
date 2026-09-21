import pytest

from services.progression_capabilities import (
    ACHIEVEMENTS_SPEC,
    PROFILE_SPEC,
    build_progression_pilot_dispatcher,
    dispatch_achievements,
    dispatch_profile,
)


class FakeProgressionDataSource:
    def __init__(self):
        self.calls = []

    async def get_level_info(self, user_id):
        self.calls.append(("level", user_id))
        return {"level": 4, "percentage": 50.0}

    async def get_weekly_xp_leaderboard(self, guild_id, limit):
        return []

    def current_week_key(self):
        return "2026-W39"

    async def get_user_weekly_xp(self, guild_id, user_id):
        self.calls.append(("weekly_xp", guild_id, user_id))
        return 70

    async def get_weekly_rank(self, guild_id, user_id):
        self.calls.append(("weekly_rank", guild_id, user_id))
        return 3

    async def get_message_leaderboard(self, guild_id, limit):
        return []

    async def get_ai_leaderboard(self, guild_id, limit):
        return []

    async def get_achievement_leaderboard(self, guild_id, limit):
        return []

    async def evaluate_progress_unlocks(self, guild_id, user_id):
        self.calls.append(("evaluate", guild_id, user_id))
        return {"achievements": [], "titles": []}

    async def get_user_stats(self, guild_id, user_id):
        self.calls.append(("stats", guild_id, user_id))
        return {"message_count": 10}

    async def get_user_achievements(self, guild_id, user_id):
        self.calls.append(("achievements", guild_id, user_id))
        return [("first", "2026-01-01")]

    async def get_user_titles(self, guild_id, user_id):
        self.calls.append(("titles", guild_id, user_id))
        return [("member", "2026-01-01")]

    async def get_equipped_title(self, guild_id, user_id):
        self.calls.append(("equipped", guild_id, user_id))
        return "member"


def test_profile_and_achievements_are_read_policy_with_bookkeeping():
    assert PROFILE_SPEC.requires_confirmation is False
    assert ACHIEVEMENTS_SPEC.requires_confirmation is False
    assert PROFILE_SPEC.slash_command == "/profile"
    assert ACHIEVEMENTS_SPEC.slash_command == "/achievements"


@pytest.mark.asyncio
async def test_profile_handler_preserves_legacy_call_order_and_bundle():
    source = FakeProgressionDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_profile(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        target_user_id=99,
    )

    assert source.calls == [
        ("evaluate", 456, 99),
        ("level", 99),
        ("stats", 456, 99),
        ("achievements", 456, 99),
        ("titles", 456, 99),
        ("equipped", 456, 99),
        ("weekly_xp", 456, 99),
        ("weekly_rank", 456, 99),
    ]
    assert result.value == {
        "level_info": {"level": 4, "percentage": 50.0},
        "stats": {"message_count": 10},
        "achievements": [("first", "2026-01-01")],
        "titles": [("member", "2026-01-01")],
        "equipped_key": "member",
        "weekly_xp": 70,
        "weekly_rank": 3,
    }


@pytest.mark.asyncio
async def test_achievements_handler_preserves_unlock_evaluation_before_read():
    source = FakeProgressionDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_achievements(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        target_user_id=99,
    )

    assert source.calls == [
        ("evaluate", 456, 99),
        ("achievements", 456, 99),
    ]
    assert result.value["rows"] == [("first", "2026-01-01")]
