"""Monthly schedule, configuration and delivery regression tests."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from cogs.admin_runtime import AdminCommands
from cogs.background import BackgroundTasksCog, SCHEDULE_TZ
from services.admin_capabilities import CONFIG_MONTHLY_SPEC


def test_monthly_and_memory_schedules_use_real_jst_offset():
    assert SCHEDULE_TZ.key == "Asia/Tokyo"
    assert datetime(2026, 11, 1, 7, tzinfo=SCHEDULE_TZ).utcoffset() == timedelta(hours=9)
    assert BackgroundTasksCog.loop_monthly.time[0].utcoffset() == timedelta(hours=9)
    assert BackgroundTasksCog.loop_memory_cleanup.time[0].utcoffset() == timedelta(hours=9)
    assert (BackgroundTasksCog.loop_monthly.time[0].hour,
            BackgroundTasksCog.loop_monthly.time[0].minute) == (7, 0)
    assert (BackgroundTasksCog.loop_memory_cleanup.time[0].hour,
            BackgroundTasksCog.loop_memory_cleanup.time[0].minute) == (4, 0)


def make_monthly_bot(rows, channels):
    async def rules():
        return rows

    bot = SimpleNamespace()
    bot.services = SimpleNamespace(maintenance=SimpleNamespace(get_monthly_rules=rules))
    bot.get_channel = lambda identifier: channels.get(identifier)
    fetched = []

    async def fetch(identifier):
        fetched.append(identifier)
        return channels.get(identifier)

    bot.fetch_channel = fetch
    return bot, fetched


@pytest.mark.asyncio
async def test_monthly_delivery_uses_target_not_rule_and_logs_success(monkeypatch, caplog):
    fixed = datetime(2026, 12, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    monkeypatch.setattr("cogs.background.datetime", SimpleNamespace(now=lambda tz: fixed))
    delivered = []
    async def send(text):
        delivered.append(text)
    target = SimpleNamespace(send=send, guild=SimpleNamespace(id=12))
    bot, fetched = make_monthly_bot([(100, 200)], {200: target})
    with caplog.at_level("INFO"):
        await BackgroundTasksCog.loop_monthly.coro(SimpleNamespace(bot=bot))
    assert fetched == []
    assert len(delivered) == 1
    assert "<#100>" in delivered[0]
    assert "\\n" not in delivered[0]
    assert "\n" in delivered[0]
    assert "target=200" in caplog.text
    assert "sent=1 failed=0 skipped=0" in caplog.text


@pytest.mark.asyncio
async def test_monthly_delivery_recovers_cache_miss_and_isolates_failures(monkeypatch, caplog):
    fixed = datetime(2026, 12, 1, 7, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    monkeypatch.setattr("cogs.background.datetime", SimpleNamespace(now=lambda tz: fixed))
    sent = []
    async def fail(text):
        raise PermissionError("forbidden")
    async def succeed(text):
        sent.append(text)
    a = SimpleNamespace(send=fail, guild=SimpleNamespace(id=1))
    b = SimpleNamespace(send=succeed, guild=SimpleNamespace(id=2))
    bot, fetched = make_monthly_bot([(10, 20), (11, 21)], {20: a, 21: b})
    # The second channel is not in the bot's cache, but is fetchable.
    bot.get_channel = lambda channel_id: {20: a}.get(channel_id)
    with caplog.at_level("INFO"):
        await BackgroundTasksCog.loop_monthly.coro(SimpleNamespace(bot=bot))
    assert fetched == [21]
    assert len(sent) == 1
    assert "<#11>" in sent[0]
    assert "target=20" in caplog.text
    assert "sent=1 failed=1 skipped=0" in caplog.text


@pytest.mark.asyncio
async def test_monthly_delivery_only_runs_on_first_day(monkeypatch):
    monkeypatch.setattr(
        "cogs.background.datetime",
        SimpleNamespace(now=lambda tz: datetime(2026, 12, 2, tzinfo=ZoneInfo("Asia/Tokyo"))),
    )
    async def rules():
        raise AssertionError("should not read rules on other days")
    bot = SimpleNamespace(services=SimpleNamespace(maintenance=SimpleNamespace(get_monthly_rules=rules)))
    await BackgroundTasksCog.loop_monthly.coro(SimpleNamespace(bot=bot))


@pytest.mark.asyncio
@pytest.mark.parametrize("target_exists,can_send", [
    (False, False), (True, False), (True, True),
])
async def test_monthly_configuration_validates_target_before_db_write(
    monkeypatch, target_exists, can_send
):
    class Channel:
        def __init__(self, identifier):
            self.id = identifier

        def permissions_for(self, member):
            return SimpleNamespace(view_channel=True, send_messages=can_send)

    monkeypatch.setattr("cogs.admin_runtime.discord.TextChannel", Channel)
    rule = Channel(100)
    target = Channel(200) if target_exists else None
    guild = SimpleNamespace(
        id=5, me=object(),
        get_channel=lambda identifier: {100: rule, 200: target}.get(identifier),
    )
    writes = []
    async def execute(sql, args):
        writes.append((sql, args))
    fake = SimpleNamespace(bot=SimpleNamespace(db=SimpleNamespace(_execute=execute)))
    context = SimpleNamespace(interaction=SimpleNamespace(
        guild=guild, user=SimpleNamespace(id=55)
    ))
    if target_exists and can_send:
        result = await AdminCommands.perform_admin_action(
            fake, context=context, capability_id=CONFIG_MONTHLY_SPEC.capability_id,
            arguments={"rule_ch_id": 100, "target_ch_id": 200},
        )
        assert result["rule_ch_id"] == 100 and result["target_ch_id"] == 200
        assert len(writes) == 1 and writes[0][1] == (5, 100, 200)
    else:
        with pytest.raises(ValueError, match="monthly_"):
            await AdminCommands.perform_admin_action(
                fake, context=context, capability_id=CONFIG_MONTHLY_SPEC.capability_id,
                arguments={"rule_ch_id": 100, "target_ch_id": 200},
            )
        assert not writes
