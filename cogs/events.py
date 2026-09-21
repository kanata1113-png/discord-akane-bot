import logging

import discord
from discord.ext import commands

from cogs.event_handlers import EventsCog as LegacyEventHandlersCog
from config import Config
from views.reaction_translation_view import ReactionTranslationView


logger = logging.getLogger("AkaneBot")


class EventsCog(LegacyEventHandlersCog):
    """Discord event handlers without background scheduler ownership.

    The legacy handler remains compatibility-preserved in ``cogs.event_handlers``.
    Reaction-add is overridden here so the old DM translation path can be
    replaced without disturbing reaction roles or starboard behavior.
    """

    async def cog_load(self):
        logger.info("EventsCog event handlers loaded.")

    def cog_unload(self):
        return None

    async def _handle_reaction_translation(
        self,
        payload: discord.RawReactionActionEvent,
        language: str,
    ) -> None:
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            return

        source = await channel.fetch_message(payload.message_id)
        if not source.content:
            return

        service = getattr(self.bot, "reaction_translation", None)
        if service is None:
            logger.warning("Reaction translation service unavailable")
            return

        key = (source.id, language)
        if service.card_is_current(source.id, language, source.content):
            card_id = service.card_ids.get(key)
            if card_id:
                try:
                    await channel.fetch_message(card_id)
                    return
                except discord.NotFound:
                    service.card_ids.pop(key, None)
                    service.card_source_hashes.pop(key, None)

        if not service.allow_user(payload.user_id):
            logger.info(
                "Reaction translation rate limited | user=%s | source=%s | language=%s",
                payload.user_id,
                source.id,
                language,
            )
            return

        translated = await service.translate(source.content, language)
        preview = service.preview(translated)
        embed = discord.Embed(
            title=f"🌐 {language} translation",
            description=preview,
            color=discord.Color.blue(),
            url=source.jump_url,
        )
        embed.set_author(
            name=source.author.display_name,
            icon_url=source.author.display_avatar.url,
        )
        embed.set_footer(
            text=f"{payload.emoji} リアクション翻訳 · GPT-5.6 Luna"
        )

        view = ReactionTranslationView(self.bot, source_url=source.jump_url)
        card_id = service.card_ids.get(key)
        card = None
        if card_id:
            try:
                card = await channel.fetch_message(card_id)
            except discord.NotFound:
                card = None

        if card is not None:
            await card.edit(embed=embed, view=view)
        else:
            card = await source.reply(
                embed=embed,
                view=view,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        service.remember_card(
            source_message_id=source.id,
            language=language,
            card_message_id=card.id,
            source_text=source.content,
        )
        logger.info(
            "Reaction translation card | user=%s | source=%s | language=%s | model=%s",
            payload.user_id,
            source.id,
            language,
            Config.FAST_MODEL,
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent,
    ):
        if self.bot.user and payload.user_id == self.bot.user.id:
            return
        if payload.member and payload.member.bot:
            return

        # Reaction roles are compatibility-preserved from the legacy handler.
        try:
            row = await self.bot.db._fetchone(
                """
                SELECT role_id
                FROM reaction_roles
                WHERE message_id=?
                AND emoji=?
                """,
                (payload.message_id, str(payload.emoji)),
            )
            if row and payload.member:
                role = payload.member.guild.get_role(row[0])
                if role:
                    await payload.member.add_roles(role)
        except Exception as error:
            logger.exception(f"Reaction role failed: {error}")

        language = Config.FLAG_MAP.get(str(payload.emoji))
        if language:
            try:
                await self._handle_reaction_translation(payload, language)
            except Exception as error:
                logger.exception(f"Reaction translation failed: {error}")

        # Starboard is compatibility-preserved from the legacy handler.
        if str(payload.emoji) == "❤️":
            try:
                channel = self.bot.get_channel(payload.channel_id)
                if not channel:
                    return
                source = await channel.fetch_message(payload.message_id)
                reaction = discord.utils.get(source.reactions, emoji="❤️")
                if not reaction or reaction.count < 10:
                    return

                posted = await self.bot.db._fetchone(
                    """
                    SELECT message_id
                    FROM starboard_log
                    WHERE message_id=?
                    """,
                    (source.id,),
                )
                if posted:
                    return

                starboard_id = await self.bot.db.get_config(
                    payload.guild_id,
                    "starboard_ch",
                )
                starboard = self.bot.get_channel(starboard_id)
                if not starboard:
                    return

                embed = discord.Embed(
                    description=source.content or "(本文なし)",
                    color=discord.Color.red(),
                    timestamp=source.created_at,
                )
                embed.set_author(
                    name=source.author.display_name,
                    icon_url=source.author.display_avatar.url,
                )
                embed.add_field(
                    name="Original",
                    value=f"[Jump]({source.jump_url})",
                )
                if source.attachments:
                    embed.set_image(url=source.attachments[0].url)

                await starboard.send(
                    "いいねがたくさん。殿堂入りやね！（茜）",
                    embed=embed,
                )
                await self.bot.db._execute(
                    """
                    INSERT INTO starboard_log
                    (message_id)
                    VALUES (?)
                    """,
                    (source.id,),
                )
            except Exception as error:
                logger.exception(f"Starboard failed: {error}")


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
