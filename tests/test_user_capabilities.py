from types import SimpleNamespace

import pytest

from services.capability_core import CapabilityContext, CapabilityRequest
from services.user_capabilities import (
    MEMORY_FORGET_CAPABILITY_ID,
    REMIND_CAPABILITY_ID,
    TITLE_SET_CAPABILITY_ID,
    build_user_capability_dispatcher,
    dispatch_memory_forget,
    dispatch_memory_status,
    dispatch_remind,
    dispatch_title_set,
    dispatch_titles,
)


class FakeDataSource:
    def __init__(self):
        self.calls = []
        self.titles = [("regular", 1, "now")]
        self.history_count = 7

    async def evaluate_progress_unlocks(self, guild_id, user_id):
        self.calls.append(("evaluate", guild_id, user_id))
        return {"achievements": [], "titles": []}

    async def get_user_titles(self, guild_id, user_id):
        self.calls.append(("titles", guild_id, user_id))
        return list(self.titles)

    async def has_title(self, guild_id, user_id, title_key):
        self.calls.append(("has_title", guild_id, user_id, title_key))
        return title_key == "regular"

    async def set_equipped_title(self, guild_id, user_id, title_key):
        self.calls.append(("set_title", guild_id, user_id, title_key))

    async def count_conversation_history(self, guild_id, channel_id, user_id):
        self.calls.append(("count", guild_id, channel_id, user_id))
        return self.history_count

    async def clear_conversation_history(self, guild_id, channel_id, user_id):
        self.calls.append(("clear_channel", guild_id, channel_id, user_id))
        return 3

    async def clear_all_user_history(self, guild_id, user_id):
        self.calls.append(("clear_all", guild_id, user_id))
        return 9

    async def add_reminder(self, user_id, channel_id, message, minutes):
        self.calls.append(("remind", user_id, channel_id, message, minutes))


@pytest.mark.asyncio
async def test_titles_preserves_unlock_evaluation_before_read():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)

    result = await dispatch_titles(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
    )

    assert result.value == {"rows": source.titles}
    assert source.calls == [
        ("evaluate", 20, 10),
        ("titles", 20, 10),
    ]


@pytest.mark.asyncio
async def test_memory_status_is_read_only():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)

    result = await dispatch_memory_status(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
    )

    assert result.value == {"count": 7}
    assert source.calls == [("count", 20, 30, 10)]


@pytest.mark.asyncio
async def test_write_capabilities_fail_closed_without_confirmation():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)
    context = CapabilityContext(user_id=10, guild_id=20, channel_id=30)

    for capability_id, arguments in (
        (TITLE_SET_CAPABILITY_ID, {"title_key": "regular"}),
        (MEMORY_FORGET_CAPABILITY_ID, {"all_channels": False}),
        (REMIND_CAPABILITY_ID, {"minutes": 5, "message": "hello"}),
    ):
        with pytest.raises(PermissionError):
            await dispatcher.dispatch(
                CapabilityRequest(capability_id, arguments),
                context,
            )

    assert source.calls == []


@pytest.mark.asyncio
async def test_title_set_requires_ownership_and_preserves_write():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)

    rejected = await dispatch_title_set(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
        title_key="missing",
        confirmed=True,
    )
    accepted = await dispatch_title_set(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
        title_key="regular",
        confirmed=True,
    )

    assert rejected.ok is False
    assert accepted.ok is True
    assert ("set_title", 20, 10, "missing") not in source.calls
    assert ("set_title", 20, 10, "regular") in source.calls


@pytest.mark.asyncio
async def test_forget_preserves_channel_vs_all_scope():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)

    one = await dispatch_memory_forget(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
        all_channels=False,
        confirmed=True,
    )
    all_result = await dispatch_memory_forget(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
        all_channels=True,
        confirmed=True,
    )

    assert one.value["deleted"] == 3
    assert all_result.value["deleted"] == 9
    assert ("clear_channel", 20, 30, 10) in source.calls
    assert ("clear_all", 20, 10) in source.calls


@pytest.mark.asyncio
async def test_remind_preserves_persistence_arguments():
    source = FakeDataSource()
    dispatcher = build_user_capability_dispatcher(source)

    result = await dispatch_remind(
        dispatcher,
        user_id=10,
        guild_id=20,
        channel_id=30,
        minutes=15,
        message="meeting",
        confirmed=True,
    )

    assert result.value == {"minutes": 15, "message": "meeting"}
    assert source.calls == [("remind", 10, 30, "meeting", 15)]
