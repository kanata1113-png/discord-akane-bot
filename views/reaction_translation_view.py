from __future__ import annotations

import io
import re

import discord

from config import Config


FULL_TRANSLATION_CUSTOM_ID = "reaction_translate_full_v1"
_TITLE_RE = re.compile(r"^🌐\s+(.+?)\s+translation$")


def _source_message_id_from_embed(embed: discord.Embed) -> int | None:
    if not embed.url:
        return None
    try:
        return int(embed.url.rstrip("/").split("/")[-1])
    except (TypeError, ValueError):
        return None


def _language_from_embed(embed: discord.Embed) -> str | None:
    if not embed.title:
        return None
    match = _TITLE_RE.match(embed.title)
    return match.group(1) if match else None


class ReactionTranslationView(discord.ui.View):
    """Persistent generic view for every public compact translation card.

    The source message is reconstructed from the embed URL, so the button keeps
    working after a bot restart without storing the translated body in Discord.
    The service cache avoids another Luna call during the normal process lifetime.
    """

    def __init__(self, bot, *, source_url: str | None = None):
        super().__init__(timeout=None)
        self.bot = bot
        if source_url:
            self.add_item(
                discord.ui.Button(
                    label="元投稿へ",
                    emoji="↗️",
                    style=discord.ButtonStyle.link,
                    url=source_url,
                )
            )

    @discord.ui.button(
        label="全文を見る",
        emoji="📖",
        style=discord.ButtonStyle.primary,
        custom_id=FULL_TRANSLATION_CUSTOM_ID,
    )
    async def show_full(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message(
                "翻訳元を見つけられへんかったわ。もう一度国旗を押してみてな。",
                ephemeral=True,
            )
            return

        embed = interaction.message.embeds[0]
        source_message_id = _source_message_id_from_embed(embed)
        language = _language_from_embed(embed)
        if source_message_id is None or language is None:
            await interaction.response.send_message(
                "翻訳元を見つけられへんかったわ。もう一度国旗を押してみてな。",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "この場所では全文を開けへんみたいや。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            source = await channel.fetch_message(source_message_id)
            service = getattr(self.bot, "reaction_translation", None)
            if service is None:
                raise RuntimeError("reaction translation service unavailable")
            translated = await service.translate(source.content, language)

            if len(translated) <= 4000:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=f"🌐 {language} translation — 全文",
                        description=translated,
                        color=discord.Color.blue(),
                        url=source.jump_url,
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "全文は長いからファイルで渡すで 📄",
                    file=discord.File(
                        io.BytesIO(translated.encode("utf-8")),
                        filename="translation.txt",
                    ),
                    ephemeral=True,
                )
        except discord.NotFound:
            await interaction.followup.send(
                "元投稿が削除されてるみたいや。",
                ephemeral=True,
            )
        except Exception:
            await interaction.followup.send(
                Config.ERROR_MSG,
                ephemeral=True,
            )
