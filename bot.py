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
    TicketCloseView,
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
    ],
)

logger = logging.getLogger(
    "AkaneBot"
)


# ==============================================================================
# Bot
# ==============================================================================

class AkaneBot(commands.Bot):

    def __init__(
        self
    ):

        intents = discord.Intents.all()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.db = DatabaseManager(
            Config.DB_NAME
        )

        self.ai = AiManager()

    # ==========================================================================
    # Setup
    # ==========================================================================

    async def setup_hook(
        self
    ):

        logger.info(
            "=============================================="
        )

        logger.info(
            "Akane Bot v34 starting..."
        )

        logger.info(
            f"Database path: "
            f"{Config.DB_NAME}"
        )

        logger.info(
            "GPT-5.6 routing:"
        )

        logger.info(
            f"  Normal chat: "
            f"{Config.CHAT_MODEL} "
            f"[{Config.CHAT_REASONING_EFFORT}]"
        )

        logger.info(
            f"  Reasoning: "
            f"{Config.REASONING_MODEL} "
            f"[{Config.REASONING_EFFORT}]"
        )

        logger.info(
            f"  Deep reasoning: "
            f"{Config.REASONING_MODEL} "
            f"[{Config.DEEP_REASONING_EFFORT}]"
        )

        logger.info(
            f"  Fast tasks: "
            f"{Config.FAST_MODEL} "
            f"[{Config.FAST_REASONING_EFFORT}]"
        )

        logger.info(
            f"Memory limit: "
            f"{Config.MEMORY_MESSAGE_LIMIT}"
        )

        logger.info(
            f"Memory retention: "
            f"{Config.MEMORY_RETENTION_DAYS} days"
        )

        logger.info(
            f"XP: "
            f"{Config.XP_PER_MESSAGE} per "
            f"{Config.XP_COOLDOWN_SECONDS}s"
        )

        logger.info(
            "OpenAI API mode: Responses API"
        )

        logger.info(
            "=============================================="
        )

        # ======================================================================
        # Database
        # ======================================================================

        try:

            await self.db.init()

            logger.info(
                f"Database initialized: "
                f"{Config.DB_NAME}"
            )

        except Exception as e:

            logger.exception(
                f"Database initialization failed: {e}"
            )

            raise

        # ======================================================================
        # Memory Cleanup
        # ======================================================================

        try:

            deleted = (
                await self.db
                .cleanup_old_conversations(
                    Config.MEMORY_RETENTION_DAYS
                )
            )

            logger.info(
                "Initial memory cleanup "
                f"completed | deleted={deleted}"
            )

        except Exception as e:

            logger.exception(
                f"Memory cleanup failed: {e}"
            )

        # ======================================================================
        # Persistent Views
        # ======================================================================

        try:

            self.add_view(
                EventView()
            )

            self.add_view(
                TicketView(
                    self
                )
            )

            self.add_view(
                TicketCloseView(
                    self
                )
            )

            logger.info(
                "Persistent views loaded."
            )

        except Exception as e:

            logger.exception(
                f"Persistent views failed: {e}"
            )

            raise

        # ======================================================================
        # Extensions
        # ======================================================================

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
                    f"Extension loaded: "
                    f"{extension}"
                )

            except Exception as e:

                logger.exception(
                    "Extension load failed "
                    f"({extension}): {e}"
                )

                raise

        # ======================================================================
        # Slash Commands
        # ======================================================================

        try:

            synced = await self.tree.sync()

            logger.info(
                f"Slash commands synced: "
                f"{len(synced)}"
            )

        except Exception as e:

            logger.exception(
                f"Command sync failed: {e}"
            )

            raise

        logger.info(
            "setup_hook completed."
        )

    # ==========================================================================
    # Ready
    # ==========================================================================

    async def on_ready(
        self
    ):

        logger.info(
            "=============================================="
        )

        logger.info(
            f"Logged in as {self.user}"
        )

        if self.user:

            logger.info(
                f"Bot user ID: "
                f"{self.user.id}"
            )

        logger.info(
            f"Discord.py version: "
            f"{discord.__version__}"
        )

        logger.info(
            f"OpenAI SDK version: "
            f"{openai.__version__}"
        )

        logger.info(
            f"Database: "
            f"{Config.DB_NAME}"
        )

        logger.info(
            f"Guild count: "
            f"{len(self.guilds)}"
        )

        logger.info(
            "GPT-5.6 model routing:"
        )

        logger.info(
            f"Normal = "
            f"{Config.CHAT_MODEL}"
        )

        logger.info(
            f"Reasoning = "
            f"{Config.REASONING_MODEL}"
        )

        logger.info(
            f"Fast = "
            f"{Config.FAST_MODEL}"
        )

        logger.info(
            "Responses API: READY"
        )

        logger.info(
            "AI memory: READY"
        )

        logger.info(
            "XP system: READY"
        )

        logger.info(
            "Spam protection: READY"
        )

        logger.info(
            "Ticket system: READY"
        )

        logger.info(
            "Achievements: READY"
        )

        logger.info(
            "Titles: READY"
        )

        logger.info(
            "Fortune: READY"
        )

        logger.info(
            "Weekly XP ranking: READY"
        )

        logger.info(
            "Community rankings: READY"
        )

        logger.info(
            "Akane Bot v34 READY"
        )

        logger.info(
            "=============================================="
        )

    # ==========================================================================
    # App Command Error
    # ==========================================================================

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):

        command_name = (
            interaction.command.name
            if interaction.command
            else "unknown"
        )

        logger.exception(
            "Global app command error | "
            f"command={command_name} | "
            f"user={interaction.user.id} | "
            f"error={error}"
        )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    "ごめん、コマンド処理中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

            else:

                await interaction.response.send_message(
                    "ごめん、コマンド処理中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

        except Exception as e:

            logger.exception(
                f"Error response failed: {e}"
            )

    # ==========================================================================
    # Discord Event Error
    # ==========================================================================

    async def on_error(
        self,
        event_method,
        *args,
        **kwargs,
    ):

        logger.exception(
            "Unhandled Discord event error | "
            f"event={event_method}"
        )


# ==============================================================================
# Bot Instance
# ==============================================================================

bot = AkaneBot()


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":

    if not Config.DISCORD_TOKEN:

        logger.error(
            "DISCORD_TOKEN is missing."
        )

    else:

        logger.info(
            "Starting Discord connection..."
        )

        try:

            bot.run(
                Config.DISCORD_TOKEN
            )

        except discord.LoginFailure:

            logger.exception(
                "Discord login failed."
            )

        except KeyboardInterrupt:

            logger.info(
                "Akane Bot stopped by user."
            )

        except Exception as e:

            logger.exception(
                f"Akane Bot fatal error: {e}"
            )
