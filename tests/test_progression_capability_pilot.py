from types import SimpleNamespace

import pytest

from cogs.general import GeneralCog
from services.progression_capabilities import (
    LEVEL_CAPABILITY_ID,
    LEVEL_SPEC,
    build_progression_pilot_dispatcher,
    dispatch_level,
)


class FakeLevelDataSource:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {
            "level": 3,
            "xp": 40,
            "required_xp": 300,
            "remaining_xp": 260,
            "percentage": 13.3,
        }
        self.error = error
        self.user_ids = []

    async def get_level_info(self, user_id):
        self.user_ids.append(user_id)
        if self.error:
            raise self.error
        return dict(self.payload)


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeInteraction:
    def __init__(self, user_id=123, guild_id=456, channel_id=789):
        self.user = SimpleNamespace(id=user_id)
        self.guild = SimpleNamespace(id=guild_id) if guild_id is not None else None
        self.channel_id = channel_id
        self.response = FakeResponse()


def test_level_spec_is_read_only_and_slash_addressable():
    assert LEVEL_SPEC.capability_id == LEVEL_CAPABILITY_ID
    assert LEVEL_SPEC.slash_command == "/level"
    assert LEVEL_SPEC.requires_confirmation is False
    assert LEVEL_SPEC.discoverable is True


@pytest.mark.asyncio
async def test_level_dispatcher_preserves_existing_data_source_payload():
    source = FakeLevelDataSource()
    dispatcher = build_progression_pilot_dispatcher(source)

    result = await dispatch_level(
        dispatcher,
        user_id=123,
        guild_id=456,
        channel_id=789,
    )

    assert result.ok is True
    assert result.capability_id == "level"
    assert result.value == source.payload
    assert source.user_ids == [123]


@pytest.mark.asyncio
async def test_level_slash_command_uses_capability_path_and_preserves_output():
    source = FakeLevelDataSource()
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()

    await GeneralCog.level.callback(cog, interaction)

    assert source.user_ids == [123]
    assert interaction.response.messages == [
        (
            "📊 **Lv.3**\n"
            "✨ XP: **40 / 300**\n"
            "🎯 次まであと **260 XP**",
            {"ephemeral": True},
        )
    ]


@pytest.mark.asyncio
async def test_level_slash_command_preserves_legacy_error_message():
    source = FakeLevelDataSource(error=RuntimeError("db unavailable"))
    cog = GeneralCog(SimpleNamespace(db=source))
    interaction = FakeInteraction()

    await GeneralCog.level.callback(cog, interaction)

    assert source.user_ids == [123]
    assert interaction.response.messages == [
        (
            "レベル情報を取得できへんかったわ。",
            {"ephemeral": True},
        )
    ]
