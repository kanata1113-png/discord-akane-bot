import logging

from datetime import datetime, time
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from config import Config, JST


logger = logging.getLogger("AkaneBot")

# pytz timezone objects must not be passed directly as datetime.time.tzinfo:
# pytz then uses its historic +09:19 LMT offset for Asia/Tokyo.
SCHEDULE_TZ = ZoneInfo("Asia/Tokyo")


class BackgroundTasksCog(commands.Cog):
    """Scheduled maintenance previously owned by EventsCog."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.loop_reminders.start()
        self.loop_monthly.start()
        self.loop_memory_cleanup.start()
        logger.info("BackgroundTasksCog tasks started.")

    def cog_unload(self):
        self.loop_reminders.cancel()
        self.loop_monthly.cancel()
        self.loop_memory_cleanup.cancel()

    @tasks.loop(seconds=60)
    async def loop_reminders(self):
        try:
            rows = await self.bot.services.maintenance.list_due_reminders()

            for reminder_id, user_id, channel_id, reminder_message in rows:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    logger.warning(
                        "Reminder channel unavailable; keeping reminder pending | "
                        f"reminder_id={reminder_id} channel_id={channel_id}"
                    )
                    continue

                try:
                    await channel.send(
                        f"⏰ <@{user_id}> リマインダー: {reminder_message}"
                    )
                    await self.bot.services.maintenance.delete_reminder(reminder_id)
                except Exception as error:
                    logger.exception(
                        "Reminder send failed; keeping reminder pending | "
                        f"reminder_id={reminder_id} error={error}"
                    )

        except Exception as error:
            logger.exception(f"Reminder loop failed: {error}")

    @loop_reminders.before_loop
    async def before_loop_reminders(self):
        await self.bot.wait_until_ready()

    @tasks.loop(
        time=time(
            hour=7,
            minute=0,
            tzinfo=SCHEDULE_TZ,
        )
    )
    async def loop_monthly(self):
        # The scheduled callback is daily at 07:00 JST, but delivery is monthly.
        if datetime.now(SCHEDULE_TZ).day != 1:
            return

        try:
            rows = await self.bot.services.maintenance.get_monthly_rules()
        except Exception:
            logger.exception("Monthly rules lookup failed")
            return

        logger.info("Monthly delivery started | configured=%s", len(rows))
        sent = 0
        failed = 0
        skipped = 0
        for rule_id, target_id in rows:
            # Each guild must be independent; one failure must not block others.
            try:
                channel = self.bot.get_channel(target_id)
                if channel is None:
                    # Cache misses must not silently suppress configured delivery.
                    channel = await self.bot.fetch_channel(target_id)
                if not hasattr(channel, "send"):
                    skipped += 1
                    logger.warning(
                        "Monthly target is not a message channel | target=%s rule=%s",
                        target_id, rule_id,
                    )
                    continue
                await channel.send(
                    "表現の自由界隈のみなさん、"
                    "おはよーさん！☀️ "
                    "新しい一ヶ月が始まったで〜！🚀\n"
                    f"📌 **ルールブック:** <#{rule_id}>\n"
                    "みんなが快適に過ごすための大事なお約束やから、まだの人はちゃんと目を通しておいてな！"
                )
                sent += 1
                logger.info(
                    "Monthly notification delivered | guild=%s target=%s rule=%s",
                    getattr(getattr(channel, "guild", None), "id", None),
                    target_id, rule_id,
                )
            except Exception:
                failed += 1
                logger.exception(
                    "Monthly notification delivery failed | target=%s rule=%s",
                    target_id, rule_id,
                )

        logger.info(
            "Monthly delivery completed | configured=%s sent=%s failed=%s skipped=%s",
            len(rows), sent, failed, skipped,
        )

    @loop_monthly.before_loop
    async def before_loop_monthly(self):
        await self.bot.wait_until_ready()

    @tasks.loop(
        time=time(
            hour=4,
            minute=0,
            tzinfo=SCHEDULE_TZ,
        )
    )
    async def loop_memory_cleanup(self):
        try:
            deleted = await self.bot.services.memory.cleanup_old(
                Config.MEMORY_RETENTION_DAYS
            )
            if deleted:
                logger.info(f"Memory cleanup: {deleted}")
        except Exception as error:
            logger.exception(f"Memory cleanup failed: {error}")

    @loop_memory_cleanup.before_loop
    async def before_memory_cleanup(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(BackgroundTasksCog(bot))
