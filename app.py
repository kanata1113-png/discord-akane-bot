import logging

import discord
import openai

from discord.ext import commands

from ai_manager import AiManager
from config import Config
from database import DatabaseManager
from db_migrations import LATEST_SCHEMA_VERSION, run_migrations
from repositories import RepositoryRegistry
from views.event_view import EventView
from views.ticket_view import TicketCloseView, TicketView


logger = logging.getLogger("AkaneBot")

EXTENSIONS = (
    "cogs.admin",
    "cogs.general",
    "cogs.events",
)


class AkaneBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.all()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.db = DatabaseManager(Config.DB_NAME)
        self.repositories = RepositoryRegistry(Config.DB_NAME)
        self.repos = self.repositories
        self.ai = AiManager()

    async def setup_hook(self):
        logger.info("==============================================")
        logger.info("Akane Bot v34 starting...")
        logger.info(f"Database path: {Config.DB_NAME}")
        logger.info("GPT-5.6 routing:")
        logger.info(
            f"  Normal chat: {Config.CHAT_MODEL} "
            f"[{Config.CHAT_REASONING_EFFORT}]"
        )
        logger.info(
            f"  Reasoning: {Config.REASONING_MODEL} "
            f"[{Config.REASONING_EFFORT}]"
        )
        logger.info(
            f"  Deep reasoning: {Config.REASONING_MODEL} "
            f"[{Config.DEEP_REASONING_EFFORT}]"
        )
        logger.info(
            f"  Fast tasks: {Config.FAST_MODEL} "
            f"[{Config.FAST_REASONING_EFFORT}]"
        )
        logger.info(f"Memory limit: {Config.MEMORY_MESSAGE_LIMIT}")
        logger.info(
            f"Memory retention: {Config.MEMORY_RETENTION_DAYS} days"
        )
        logger.info(
            f"XP: {Config.XP_PER_MESSAGE} per "
            f"{Config.XP_COOLDOWN_SECONDS}s"
        )
        logger.info("OpenAI API mode: Responses API")
        logger.info("==============================================")

        try:
            await self.db.init()
            logger.info(f"Database initialized: {Config.DB_NAME}")

            applied = await run_migrations(self.db.path)
            if applied:
                logger.info(
                    "Database migrations applied | "
                    + ", ".join(
                        f"v{migration.version}:{migration.name}"
                        for migration in applied
                    )
                )
            logger.info(
                f"Database schema version: {LATEST_SCHEMA_VERSION}"
            )
        except Exception as error:
            logger.exception(f"Database initialization failed: {error}")
            raise

        try:
            deleted = await self.db.cleanup_old_conversations(
                Config.MEMORY_RETENTION_DAYS
            )
            logger.info(
                "Initial memory cleanup completed | "
                f"deleted={deleted}"
            )
        except Exception as error:
            logger.exception(f"Memory cleanup failed: {error}")

        try:
            self.add_view(EventView())
            self.add_view(TicketView(self))
            self.add_view(TicketCloseView(self))
            logger.info("Persistent views loaded.")
        except Exception as error:
            logger.exception(f"Persistent views failed: {error}")
            raise

        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info(f"Extension loaded: {extension}")
            except Exception as error:
                logger.exception(
                    f"Extension load failed ({extension}): {error}"
                )
                raise

        try:
            synced = await self.tree.sync()
            logger.info(f"Slash commands synced: {len(synced)}")
        except Exception as error:
            logger.exception(f"Command sync failed: {error}")
            raise

        logger.info("setup_hook completed.")

    async def on_ready(self):
        logger.info("==============================================")
        logger.info(f"Logged in as {self.user}")

        if self.user:
            logger.info(f"Bot user ID: {self.user.id}")

        logger.info(f"Discord.py version: {discord.__version__}")
        logger.info(f"OpenAI SDK version: {openai.__version__}")
        logger.info(f"Database: {Config.DB_NAME}")
        logger.info(f"Guild count: {len(self.guilds)}")
        logger.info("GPT-5.6 model routing:")
        logger.info(f"Normal = {Config.CHAT_MODEL}")
        logger.info(f"Reasoning = {Config.REASONING_MODEL}")
        logger.info(f"Fast = {Config.FAST_MODEL}")
        logger.info("Responses API: READY")
        logger.info("AI memory: READY")
        logger.info("XP system: READY")
        logger.info("Spam protection: READY")
        logger.info("Ticket system: READY")
        logger.info("Achievements: READY")
        logger.info("Titles: READY")
        logger.info("Fortune: READY")
        logger.info("Weekly XP ranking: READY")
        logger.info("Community rankings: READY")
        logger.info("Akane Bot v34 READY")
        logger.info("==============================================")

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
                    "ごめん、コマンド処理中にエラーが起きたで。",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "ごめん、コマンド処理中にエラーが起きたで。",
                    ephemeral=True,
                )
        except Exception as send_error:
            logger.exception(
                f"Error response failed: {send_error}"
            )

    async def on_error(self, event_method, *args, **kwargs):
        logger.exception(
            "Unhandled Discord event error | "
            f"event={event_method}"
        )


def create_bot() -> AkaneBot:
    """Create the Discord application without opening a network connection."""
    return AkaneBot()
