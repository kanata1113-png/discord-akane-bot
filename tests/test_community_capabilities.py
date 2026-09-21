from types import SimpleNamespace

import pytest

from services.capability_core import CapabilityRisk
from services.community_capabilities import (
    EVENT_CREATE_CAPABILITY_ID,
    EVENT_CREATE_SPEC,
    MESSAGE_SEARCH_CAPABILITY_ID,
    MESSAGE_SEARCH_SPEC,
    POLL_CREATE_CAPABILITY_ID,
    POLL_CREATE_SPEC,
    build_community_capability_dispatcher,
    dispatch_event_create,
    dispatch_message_search,
    dispatch_poll_create,
)


class RecordingCommunitySource:
    def __init__(self):
        self.calls = []

    async def search_messages(self, **kwargs):
        self.calls.append(("search", kwargs))
        return {"rows": ["hit"]}

    async def create_event(self, **kwargs):
        self.calls.append(("event", kwargs))
        return {"created": True}

    async def create_poll(self, **kwargs):
        self.calls.append(("poll", kwargs))
        return {"created": True}


def test_release_e_risks_are_explicit():
    assert MESSAGE_SEARCH_SPEC.risk is CapabilityRisk.READ_ONLY
    assert MESSAGE_SEARCH_SPEC.requires_confirmation is False
    assert EVENT_CREATE_SPEC.risk is CapabilityRisk.WRITE_CONFIRM
    assert EVENT_CREATE_SPEC.requires_confirmation is True
    assert POLL_CREATE_SPEC.risk is CapabilityRisk.WRITE_CONFIRM
    assert POLL_CREATE_SPEC.requires_confirmation is True


@pytest.mark.asyncio
async def test_search_dispatch_preserves_arguments():
    source = RecordingCommunitySource()
    dispatcher = build_community_capability_dispatcher(source)
    result = await dispatch_message_search(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        keyword="test",
        target_channel_id=4,
        target_user_id=5,
        days=7,
    )
    assert result.capability_id == MESSAGE_SEARCH_CAPABILITY_ID
    assert result.ok is True
    kind, call = source.calls[-1]
    assert kind == "search"
    assert call["keyword"] == "test"
    assert call["target_channel_id"] == 4
    assert call["target_user_id"] == 5
    assert call["days"] == 7


@pytest.mark.asyncio
async def test_event_requires_confirmation_before_adapter_call():
    source = RecordingCommunitySource()
    dispatcher = build_community_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_event_create(
            dispatcher,
            user_id=1,
            guild_id=2,
            channel_id=3,
            title="勉強会",
            date="2026/09/30",
            time="20:00",
            confirmed=False,
        )
    assert source.calls == []

    result = await dispatch_event_create(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        title="勉強会",
        date="2026/09/30",
        time="20:00",
        confirmed=True,
    )
    assert result.capability_id == EVENT_CREATE_CAPABILITY_ID
    assert source.calls[-1][0] == "event"


@pytest.mark.asyncio
async def test_poll_requires_confirmation_before_adapter_call():
    source = RecordingCommunitySource()
    dispatcher = build_community_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_poll_create(
            dispatcher,
            user_id=1,
            guild_id=2,
            channel_id=3,
            question="どっち？",
            options=("A", "B"),
            confirmed=False,
        )
    assert source.calls == []

    result = await dispatch_poll_create(
        dispatcher,
        user_id=1,
        guild_id=2,
        channel_id=3,
        question="どっち？",
        options=("A", "B"),
        confirmed=True,
    )
    assert result.capability_id == POLL_CREATE_CAPABILITY_ID
    assert source.calls[-1][0] == "poll"
