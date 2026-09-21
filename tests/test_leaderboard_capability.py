from types import SimpleNamespace

import pytest

from cogs.general import GeneralCog
from services.progression_capabilities import (
    LEADERBOARD_CAPABILITY_ID,
    LEADERBOARD_SPEC,
    build_progression_pilot_dispatcher,
    dispatch_leaderboard,
)


class FakeLeaderboardDataSource:
    def __init__(self, rows=None, error=None):
        self.rows = rows or [(101, 7, 640), (202, 5, 410)]
        self.error = error
        self.limits = []

    async def get_leaderboard(self, limit):
        self.limits.append(limit)
        if self.error:
            raise self.error
        return list(self.rows)


class FakeResponse:
    def __init__(self):
        self.deferred = []

    async def defer(self, **kwargs):
        self.deferred.append(kwargs)


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeGuild:
    def __init__(self):
        self.id = 456
        self.members = {
            101: SimpleNamespace(display_name="Alice"),
            202: SimpleNamespace(display_name="Bob"),
        }

    def get_member(self, user_id):
        return self.members.get(user_id)


class FakeInteraction:
    def __init__(self):
        self.user = SimpleNamespace(id=123)
        self.guild = FakeGuild()
        self.channel_id = 789
        self.response = FakeResponse()
        self.followup = FakeFollowup()


def test_leaderboard_spec_is_read_only_and_slash_addressable():
    assert LEADERBOARD_SPEC.capability_id == LEADERBOARD_CAPABILITY_ID
    assert LEADERBOARD_SPEC.slash_command == "/leaderboard"
    assert LEADERBOARD_SPEC.requires_confirmation is False


@pytest.mark.asyncio
async def test_leaderboard_dispatcher_preserves_rows_and_limit():
    source = FakeLeaderboardDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_leaderboard(
        dispatcher,
        user_id=123,
        guild_id=456,
        channel_id=789,
        limit=30,
    )

    assert result.ok is True
    assert result.capability_id == "leaderboard"
    assert result.value == {"rows": source.rows}
    assert source.limits == [30]


@pytest.mark.asyncio
async def test_leaderboard_slash_command_uses_capability_path_and_preserves_output():
    source = FakeLeaderboardDataSource()
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()

    await GeneralCog.leaderboard.callback(cog, interaction)

    assert source.limits == [30]
    assert interaction.response.deferred == [{"ephemeral": True}]
    assert len(interaction.followup.messages) == 1

    content, kwargs = interaction.followup.messages[0]
    assert content is None
    assert kwargs["ephemeral"] is True
    embed = kwargs["embed"]
    assert embed.title == "🏆 レベルランキング"
    assert embed.description == (
        "1. Alice (Lv.7 / XP 640)\n"
        "2. Bob (Lv.5 / XP 410)"
    )


@pytest.mark.asyncio
async def test_leaderboard_slash_command_preserves_legacy_error_message():
    source = FakeLeaderboardDataSource(error=RuntimeError("db unavailable"))
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()

    await GeneralCog.leaderboard.callback(cog, interaction)

    assert source.limits == [30]
    content, kwargs = interaction.followup.messages[0]
    assert content == "ランキング取得中にエラーが起きたで。"
    assert kwargs == {"ephemeral": True}
