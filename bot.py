import logging

import discord

from app import create_bot
from config import Config


logger = logging.getLogger("AkaneBot")


def configure_logging():
    """Configure runtime logging for the executable entrypoint."""
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


# Compatibility: existing imports may continue to use `from bot import bot`.
bot = create_bot()


def main():
    configure_logging()

    if not Config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is missing.")
        return

    logger.info("Starting Discord connection...")

    try:
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.exception("Discord login failed.")
    except KeyboardInterrupt:
        logger.info("Akane Bot stopped by user.")
    except Exception as error:
        logger.exception(f"Akane Bot fatal error: {error}")


if __name__ == "__main__":
    main()
