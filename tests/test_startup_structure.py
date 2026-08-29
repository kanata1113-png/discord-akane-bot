import discord

import app
import bot


def test_create_bot_returns_discord_client_without_running_it():
    client = app.create_bot()

    assert isinstance(client, discord.Client)
    assert client.is_closed() is False


def test_entrypoint_keeps_compatibility_bot_instance():
    assert isinstance(bot.bot, app.AkaneBot)


def test_main_does_not_start_when_discord_token_is_missing(monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(bot.Config, "DISCORD_TOKEN", None)
    monkeypatch.setattr(bot.bot, "run", fake_run)

    bot.main()

    assert called is False
