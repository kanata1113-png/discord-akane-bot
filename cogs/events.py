import logging

from cogs.event_handlers import EventsCog as LegacyEventHandlersCog


logger = logging.getLogger("AkaneBot")


class EventsCog(LegacyEventHandlersCog):
    """Discord event handlers without background scheduler ownership.

    The handler implementation remains compatibility-preserved in
    ``cogs.event_handlers`` during v35. Phase 6 moves lifecycle/background
    loops into ``BackgroundTasksCog`` so this extension owns only Discord
    event listeners.
    """

    async def cog_load(self):
        logger.info("EventsCog event handlers loaded.")

    def cog_unload(self):
        # Background task cancellation is owned by BackgroundTasksCog.
        return None


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
