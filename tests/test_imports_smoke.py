import importlib

import discord


MODULES = [
    "config",
    "database",
    "ai_manager",
    "views.event_view",
    "views.ticket_view",
    "cogs.admin",
    "cogs.general",
    "cogs.events",
    "bot",
]


def test_all_application_modules_import_without_external_connection():
    loaded = [importlib.import_module(module_name) for module_name in MODULES]
    assert len(loaded) == len(MODULES)


def test_bot_import_creates_bot_without_running_it():
    module = importlib.import_module("bot")

    assert isinstance(module.bot, discord.Client)
    assert module.bot.is_closed() is False
