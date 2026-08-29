import logging

from datetime import datetime, time

from discord.ext import commands, tasks

from config import Config, JST


logger = logging.getLogger("AkaneBot")


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
            rows = await self.bot.services.maintenance.claim_due_reminders()

            for reminder_id, user_id, channel_id, reminder_message in rows:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue

                try:
                    await channel.send(
                        f"⏰ <@{user_id}> リマインダー: {reminder_message}"
                    )
                except Exception as error:
                    logger.exception(f"Reminder send failed: {error}")

        except Exception as error:
            logger.exception(f"Reminder loop failed: {error}")

    @loop_reminders.before_loop
    async def before_loop_reminders(self):
        await self.bot.wait_until_ready()

    @tasks.loop(
        time=time(
            hour=7,
            minute=0,
            tzinfo=JST,
        )
    )
    async def loop_monthly(self):
        if datetime.now(JST).day != 1:
            return

        try:
            rows = await self.bot.services.maintenance.get_monthly_rules()

            for rule_id, target_id in rows:
                channel = self.bot.get_channel(target_id)
                if channel:
                    await channel.send(
                        "表現の自由界隈のみなさん、"
                        "おはよーさん！☀️ "
                        "新しい一ヶ月が始まったで〜！🚀\n"
                        "📌 **ルールブック:** <#{rule_id}>\n"
                        "みんなが快適に過ごすための大事なお約束やから、まだの人はちゃんと目を通しておいてな！"
                    )

        except Exception as error:
            logger.exception(f"Monthly loop failed: {error}")

    @loop_monthly.before_loop
    async def before_loop_monthly(self):
        await self.bot.wait_until_ready()

    @tasks.loop(
        time=time(
            hour=4,
            minute=0,
            tzinfo=JST,
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
