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

    def __init__(self):

        intents = discord.Intents.all()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        # ======================================================================
        # Managers
        # ======================================================================

        self.db = DatabaseManager(
            Config.DB_NAME
        )

        self.ai = AiManager()

    # ==========================================================================
    # Setup Hook
    # ==========================================================================

    async def setup_hook(self):

        logger.info(
            "=============================================="
        )

        logger.info(
            "Akane Bot v32 starting..."
        )

        logger.info(
            f"Database path: "
            f"{Config.DB_NAME}"
        )

        logger.info(
            f"Chat model: "
            f"{Config.CHAT_MODEL}"
        )

        logger.info(
            f"Reasoning model: "
            f"{Config.REASONING_MODEL}"
        )

        logger.info(
            f"Fast model: "
            f"{Config.FAST_MODEL}"
        )

        logger.info(
            f"Memory limit: "
            f"{Config.MEMORY_MESSAGE_LIMIT} messages"
        )

        logger.info(
            f"Memory retention: "
            f"{Config.MEMORY_RETENTION_DAYS} days"
        )

        logger.info(
            f"XP per message: "
            f"{Config.XP_PER_MESSAGE}"
        )

        logger.info(
            f"XP cooldown: "
            f"{Config.XP_COOLDOWN_SECONDS}s"
        )

        logger.info(
            "Spam protection: ENABLED"
        )

        logger.info(
            "Ticket system: V32 compatible"
        )

        logger.info(
            f"Achievements: "
            f"{len(Config.ACHIEVEMENTS)}"
        )

        logger.info(
            f"Titles: "
            f"{len(Config.TITLES)}"
        )

        logger.info(
            "Fortune system: ENABLED"
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
                "Database initialization "
                f"failed: {e}"
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

            # Memory cleanup失敗だけでは
            # Bot全体を停止させない
            logger.exception(
                "Initial memory cleanup "
                f"failed: {e}"
            )

        # ======================================================================
        # Persistent Views
        # ======================================================================

        try:

            # ------------------------------------------------------------------
            # Event
            # ------------------------------------------------------------------

            self.add_view(
                EventView()
            )

            # ------------------------------------------------------------------
            # Ticket
            # ------------------------------------------------------------------

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
                "Persistent view loading "
                f"failed: {e}"
            )

            raise

        # ======================================================================
        # Extensions / Cogs
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
                "Slash commands synced: "
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

    async def on_ready(self):

        logger.info(
            "=============================================="
        )

        logger.info(
            f"Logged in as "
            f"{self.user}"
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
            f"OpenAI version: "
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

        # ======================================================================
        # AI
        # ======================================================================

        logger.info(
            f"Chat model: "
            f"{Config.CHAT_MODEL}"
        )

        logger.info(
            f"Reasoning model: "
            f"{Config.REASONING_MODEL}"
        )

        logger.info(
            f"Fast model: "
            f"{Config.FAST_MODEL}"
        )

        logger.info(
            f"Memory message limit: "
            f"{Config.MEMORY_MESSAGE_LIMIT}"
        )

        logger.info(
            f"Memory retention days: "
            f"{Config.MEMORY_RETENTION_DAYS}"
        )

        # ======================================================================
        # XP
        # ======================================================================

        logger.info(
            f"XP: "
            f"{Config.XP_PER_MESSAGE} "
            f"per "
            f"{Config.XP_COOLDOWN_SECONDS}s"
        )

        # ======================================================================
        # V31
        # ======================================================================

        logger.info(
            "Spam protection: READY"
        )

        logger.info(
            "Ticket system: READY"
        )

        # ======================================================================
        # V32
        # ======================================================================

        logger.info(
            f"Achievements: "
            f"{len(Config.ACHIEVEMENTS)} READY"
        )

        logger.info(
            f"Titles: "
            f"{len(Config.TITLES)} READY"
        )

        logger.info(
            "Fortune system: READY"
        )

        logger.info(
            "Profile system: READY"
        )

        logger.info(
            "Akane Bot v32 READY"
        )

        logger.info(
            "=============================================="
        )

    # ==========================================================================
    # Global App Command Error Handler
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

        error_message = (
            "ごめん、コマンド処理中に"
            "エラーが起きたで。"
        )

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    error_message,
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    error_message,
                    ephemeral=True,
                )

        except Exception as send_error:

            logger.exception(
                "Failed to send app command "
                f"error message: {send_error}"
            )

    # ==========================================================================
    # Discord Event Error Handler
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
            "=============================================="
        )

        logger.error(
            "DISCORD_TOKEN is missing."
        )

        logger.error(
            "Railway Variables または "
            ".env を確認してください。"
        )

        logger.error(
            "=============================================="
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
                "Discord login failed. "
                "DISCORD_TOKENを確認してください。"
            )

        except KeyboardInterrupt:

            logger.info(
                "Akane Bot stopped by user."
            )

        except Exception as e:

            logger.exception(
                f"Akane Bot fatal error: {e}"
            )
