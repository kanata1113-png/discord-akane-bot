import logging

import discord
import openai

from discord.ext import commands

from config import Config
from database import DatabaseManager
from ai_manager import AiManager

from views.event_view import EventView
from views.ticket_view import (
    TicketView,
    TicketCloseView
)


# ==============================================================================
# Logging
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AkaneBot")


# ==============================================================================
# Bot
# ==============================================================================

class AkaneBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.all()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

        self.db = DatabaseManager(
            Config.DB_NAME
        )

        self.ai = AiManager()

    # ==========================================================================
    # Setup
    # ==========================================================================

    async def setup_hook(self):

        logger.info(
            "=============================================="
        )

        logger.info(
            "Akane Bot v28 starting..."
        )

        logger.info(
            f"Database path: {Config.DB_NAME}"
        )

        logger.info(
            f"AI model: {Config.GPT_MODEL}"
        )

        logger.info(
            "=============================================="
        )

        # ----------------------------------------------------------------------
        # Database
        # ----------------------------------------------------------------------

        await self.db.init()

        logger.info(
            f"Database initialized: {Config.DB_NAME}"
        )

        # ----------------------------------------------------------------------
        # Persistent Views
        # ----------------------------------------------------------------------

        self.add_view(
            EventView()
        )

        self.add_view(
            TicketView()
        )

        self.add_view(
            TicketCloseView()
        )

        logger.info(
            "Persistent views loaded."
        )

        # ----------------------------------------------------------------------
        # Cogs
        # ----------------------------------------------------------------------

        extensions = [
            "cogs.admin",
            "cogs.general",
            "cogs.events",
        ]

        for extension in extensions:

            try:

                await self.load_extension(
                    extension
                )

                logger.info(
                    f"Extension loaded: {extension}"
                )

            except Exception as e:

                logger.exception(
                    f"Extension load failed "
                    f"({extension}): {e}"
                )

                raise

        # ----------------------------------------------------------------------
        # Slash Commands
        # ----------------------------------------------------------------------

        try:

            synced = await self.tree.sync()

            logger.info(
                f"Slash commands synced: {len(synced)}"
            )

        except Exception as e:

            logger.exception(
                f"Command sync failed: {e}"
            )

            raise

    # ==========================================================================
    # Ready
    # ==========================================================================

    async def on_ready(self):

        logger.info(
            "=============================================="
        )

        logger.info(
            f"Logged in as {self.user}"
        )

        logger.info(
            f"Discord.py version: {discord.__version__}"
        )

        logger.info(
            f"OpenAI version: {openai.__version__}"
        )

        logger.info(
            f"Database: {Config.DB_NAME}"
        )

        logger.info(
            f"Guild count: {len(self.guilds)}"
        )

        logger.info(
            "Akane Bot v28 READY"
        )

        logger.info(
            "=============================================="
        )


# ==============================================================================
# Main
# ==============================================================================

bot = AkaneBot()


if __name__ == "__main__":

    if not Config.DISCORD_TOKEN:

        logger.error(
            "DISCORD_TOKEN is missing."
        )

    else:

        bot.run(
            Config.DISCORD_TOKEN
        )
