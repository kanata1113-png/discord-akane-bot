import pytest

from services.capability_core import CapabilityRisk
from services.moderation_capabilities import (
    BAN_SPEC,
    KICK_SPEC,
    MODERATION_CAPABILITY_SPECS,
    PURGE_SPEC,
    build_moderation_capability_dispatcher,
    dispatch_ban,
    dispatch_kick,
    dispatch_purge,
)


class FakeModerationDataSource:
    def __init__(self):
        self.calls = []

    async def kick_member(self, *, context, target_user_id):
        self.calls.append(("kick", target_user_id))
        return {"target_user_id": target_user_id}

    async def ban_member(self, *, context, target_user_id):
        self.calls.append(("ban", target_user_id))
        return {"target_user_id": target_user_id}

    async def purge_messages(self, *, context, amount, target_user_id, hours):
        self.calls.append(("purge", amount, target_user_id, hours))
        return {"deleted": amount}


def test_moderation_specs_are_hidden_and_confirmation_gated():
    assert MODERATION_CAPABILITY_SPECS == (KICK_SPEC, BAN_SPEC, PURGE_SPEC)
    for spec in MODERATION_CAPABILITY_SPECS:
        assert spec.risk is CapabilityRisk.MODERATION
        assert spec.requires_confirmation is True
        assert spec.discoverable is False
        assert spec.slash_command.startswith("/admin ")


@pytest.mark.asyncio
async def test_kick_fails_closed_without_confirmation():
    source = FakeModerationDataSource()
    dispatcher = build_moderation_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_kick(
            dispatcher,
            user_id=1,
            guild_id=2,
            channel_id=3,
            target_user_id=4,
            confirmed=False,
        )
    assert source.calls == []


@pytest.mark.asyncio
async def test_ban_fails_closed_without_confirmation():
    source = FakeModerationDataSource()
    dispatcher = build_moderation_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_ban(
            dispatcher,
            user_id=1,
            guild_id=2,
            channel_id=3,
            target_user_id=4,
            confirmed=False,
        )
    assert source.calls == []


@pytest.mark.asyncio
async def test_purge_fails_closed_without_confirmation():
    source = FakeModerationDataSource()
    dispatcher = build_moderation_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_purge(
            dispatcher,
            user_id=1,
            guild_id=2,
            channel_id=3,
            amount=50,
            target_user_id=None,
            hours=None,
            confirmed=False,
        )
    assert source.calls == []


@pytest.mark.asyncio
async def test_confirmed_moderation_reaches_adapter():
    source = FakeModerationDataSource()
    dispatcher = build_moderation_capability_dispatcher(source)
    await dispatch_kick(dispatcher, user_id=1, guild_id=2, channel_id=3, target_user_id=4, confirmed=True)
    await dispatch_ban(dispatcher, user_id=1, guild_id=2, channel_id=3, target_user_id=5, confirmed=True)
    await dispatch_purge(dispatcher, user_id=1, guild_id=2, channel_id=3, amount=25, target_user_id=6, hours=12, confirmed=True)
    assert source.calls == [("kick", 4), ("ban", 5), ("purge", 25, 6, 12)]
