from types import SimpleNamespace

import pytest

from cogs.general import GeneralCog
from services.progression_capabilities import (
    RANKINGS_SPEC,
    WEEKLY_SPEC,
    build_progression_pilot_dispatcher,
    dispatch_rankings,
    dispatch_weekly,
)


class FakeProgressionDataSource:
    def __init__(self):
        self.calls = []

    async def get_level_info(self, user_id):
        return {}

    async def get_weekly_xp_leaderboard(self, guild_id, limit):
        self.calls.append(("weekly_rows", guild_id, limit))
        return [(10, 120), (20, 80)]

    def current_week_key(self):
        self.calls.append(("week_key",))
        return "2026-W39"

    async def get_user_weekly_xp(self, guild_id, user_id):
        self.calls.append(("user_weekly", guild_id, user_id))
        return 80

    async def get_weekly_rank(self, guild_id, user_id):
        self.calls.append(("weekly_rank", guild_id, user_id))
        return 2

    async def get_message_leaderboard(self, guild_id, limit):
        self.calls.append(("messages", guild_id, limit))
        return [(10, 44)]

    async def get_ai_leaderboard(self, guild_id, limit):
        self.calls.append(("ai", guild_id, limit))
        return [(10, 12)]

    async def get_achievement_leaderboard(self, guild_id, limit):
        self.calls.append(("achievements", guild_id, limit))
        return [(10, 5)]


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeGuild:
    def __init__(self, guild_id=456):
        self.id = guild_id

    def get_member(self, user_id):
        names = {10: "Alice", 20: "Bob"}
        name = names.get(user_id)
        return SimpleNamespace(display_name=name) if name else None


class FakeInteraction:
    def __init__(self):
        self.user = SimpleNamespace(id=20)
        self.guild = FakeGuild()
        self.channel_id = 789
        self.response = FakeResponse()


def test_ranking_specs_are_read_only():
    assert WEEKLY_SPEC.slash_command == "/weekly"
    assert RANKINGS_SPEC.slash_command == "/rankings"
    assert WEEKLY_SPEC.requires_confirmation is False
    assert RANKINGS_SPEC.requires_confirmation is False


@pytest.mark.asyncio
async def test_weekly_dispatcher_preserves_query_bundle():
    source = FakeProgressionDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_weekly(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        limit=10,
    )

    assert result.value == {
        "rows": [(10, 120), (20, 80)],
        "week_key": "2026-W39",
        "user_xp": 80,
        "user_rank": 2,
    }
    assert source.calls == [
        ("weekly_rows", 456, 10),
        ("week_key",),
        ("user_weekly", 456, 20),
        ("weekly_rank", 456, 20),
    ]


@pytest.mark.parametrize(
    ("category", "expected_title", "expected_suffix", "expected_call"),
    [
        ("weekly", "🔥 週間XPランキング", "XP", ("weekly_rows", 456, 10)),
        ("messages", "💬 発言数ランキング", "発言", ("messages", 456, 10)),
        ("ai", "🤖 AI会話ランキング", "回", ("ai", 456, 10)),
        ("achievements", "🏆 実績ランキング", "個", ("achievements", 456, 10)),
    ],
)
@pytest.mark.asyncio
async def test_rankings_dispatcher_preserves_categories(
    category,
    expected_title,
    expected_suffix,
    expected_call,
):
    source = FakeProgressionDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_rankings(
        dispatcher,
        user_id=20,
        guild_id=456,
        channel_id=789,
        category=category,
        limit=10,
    )

    assert result.value["title"] == expected_title
    assert result.value["suffix"] == expected_suffix
    assert source.calls == [expected_call]


@pytest.mark.asyncio
async def test_weekly_slash_preserves_embed_shape():
    source = FakeProgressionDataSource()
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()

    await GeneralCog.weekly.callback(cog, interaction)

    content, kwargs = interaction.response.messages[0]
    embed = kwargs["embed"]
    assert content is None
    assert embed.title == "🔥 今週のXPランキング"
    assert "🥇 **Alice** — **120 XP**" in embed.description
    assert "🥈 **Bob** — **80 XP**" in embed.description
    assert embed.fields[0].name == "あなた"
    assert "XP: **80**" in embed.fields[0].value
    assert "#2" in embed.fields[0].value
    assert embed.footer.text == "2026-W39 / JST・月曜〜日曜"


@pytest.mark.asyncio
async def test_rankings_slash_preserves_embed_shape():
    source = FakeProgressionDataSource()
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()
    category = SimpleNamespace(value="messages")

    await GeneralCog.rankings.callback(cog, interaction, category)

    content, kwargs = interaction.response.messages[0]
    embed = kwargs["embed"]
    assert content is None
    assert embed.title == "💬 発言数ランキング"
    assert "🥇 **Alice** — **44 発言**" in embed.description
    assert embed.footer.text.endswith("・このサーバー内のみ")
