import io
import logging
import re

from collections import defaultdict, deque
from datetime import datetime, time

import discord
from discord.ext import commands, tasks

from config import Config, JST


logger = logging.getLogger("AkaneBot")


class EventsCog(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.spam_check = defaultdict(
            lambda: deque(
                maxlen=5
            )
        )

    async def cog_load(self):

        self.loop_reminders.start()
        self.loop_monthly.start()

    def cog_unload(self):

        self.loop_reminders.cancel()
        self.loop_monthly.cancel()

    # ==========================================================================
    # Reminder Loop
    # ==========================================================================

    @tasks.loop(seconds=60)
    async def loop_reminders(self):

        try:

            now_str = datetime.now(
                JST
            ).isoformat()

            rows = await self.bot.db._fetchall(
                """
                SELECT
                    id,
                    user_id,
                    channel_id,
                    message
                FROM reminders
                WHERE end_time <= ?
                """,
                (
                    now_str,
                )
            )

            if not rows:
                return

            ids = [
                row[0]
                for row in rows
            ]

            placeholders = ",".join(
                "?"
                for _ in ids
            )

            await self.bot.db._execute(
                f"""
                DELETE FROM reminders
                WHERE id IN ({placeholders})
                """,
                ids
            )

            for (
                reminder_id,
                user_id,
                channel_id,
                reminder_message
            ) in rows:

                channel = self.bot.get_channel(
                    channel_id
                )

                if not channel:

                    logger.warning(
                        "Reminder channel not found "
                        f"(channel={channel_id})"
                    )

                    continue

                try:

                    await channel.send(
                        f"⏰ <@{user_id}> "
                        f"リマインダー: "
                        f"{reminder_message}"
                    )

                except Exception as e:

                    logger.exception(
                        "Reminder send failed "
                        f"(id={reminder_id}): {e}"
                    )

        except Exception as e:

            logger.exception(
                f"Reminder loop failed: {e}"
            )

    @loop_reminders.before_loop
    async def before_loop_reminders(self):

        await self.bot.wait_until_ready()

    # ==========================================================================
    # Monthly Loop
    # ==========================================================================

    @tasks.loop(
        time=time(
            hour=7,
            minute=0,
            tzinfo=JST
        )
    )
    async def loop_monthly(self):

        if datetime.now(JST).day != 1:
            return

        try:

            rows = await self.bot.db._fetchall(
                """
                SELECT rule_ch, target_ch
                FROM monthly_rules
                """
            )

            for rule_id, target_id in rows:

                channel = self.bot.get_channel(
                    target_id
                )

                if not channel:

                    logger.warning(
                        "Monthly target channel "
                        f"not found: {target_id}"
                    )

                    continue

                message = (
                    "表現の自由界隈のみなさん、"
                    "おはよーさん！☀️ "
                    "新しい一ヶ月が始まったで〜！🚀\n"
                    f"📌 **ルールブック:** "
                    f"<#{rule_id}>\n"
                    "目を通しておいてな！"
                )

                try:

                    await channel.send(
                        message
                    )

                except Exception as e:

                    logger.exception(
                        "Monthly notification failed "
                        f"(channel={target_id}): {e}"
                    )

        except Exception as e:

            logger.exception(
                f"Monthly loop failed: {e}"
            )

    @loop_monthly.before_loop
    async def before_loop_monthly(self):

        await self.bot.wait_until_ready()

    # ==========================================================================
    # Messages
    # ==========================================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        if (
            message.author.bot
            or not message.guild
        ):
            return

        # ----------------------------------------------------------------------
        # Spam
        # ----------------------------------------------------------------------

        now = datetime.now().timestamp()

        history = self.spam_check[
            message.author.id
        ]

        history.append(now)

        if (
            len(history) == 5
            and history[-1] - history[0] < 5
            and not message.author.guild_permissions.administrator
        ):

            await message.channel.send(
                f"{message.author.mention} "
                "連投はやめてな！",
                delete_after=5
            )

            return

        # ----------------------------------------------------------------------
        # NG words
        # ----------------------------------------------------------------------

        try:

            ng_words = await self.bot.db._fetchall(
                """
                SELECT word
                FROM ng_words
                WHERE guild_id=?
                """,
                (
                    message.guild.id,
                )
            )

            for (word,) in ng_words:

                if word in message.content:

                    await message.delete()

                    await message.channel.send(
                        f"{message.author.mention} "
                        "NGワードやで！",
                        delete_after=3
                    )

                    return

        except discord.Forbidden:

            logger.warning(
                "NG word moderation permission denied."
            )

        except Exception as e:

            logger.exception(
                f"NG word processing failed: {e}"
            )

        # ----------------------------------------------------------------------
        # Auto reply
        # ----------------------------------------------------------------------

        try:

            result = await self.bot.db._fetchone(
                """
                SELECT response
                FROM auto_replies
                WHERE guild_id=?
                AND trigger=?
                """,
                (
                    message.guild.id,
                    message.content
                )
            )

            if result:

                await message.channel.send(
                    result[0]
                )

                return

        except Exception as e:

            logger.exception(
                f"Auto reply failed: {e}"
            )

        # ----------------------------------------------------------------------
        # AI Chat - v29 Memory
        # ----------------------------------------------------------------------

        try:

            auto_chat_channel = (
                await self.bot.db.get_config(
                    message.guild.id,
                    "auto_chat_ch"
                )
            )

            is_target = (
                self.bot.user in message.mentions
                or message.channel.id
                == auto_chat_channel
            )

            if is_target:

                clean_text = re.sub(
                    r"<@!?\d+>",
                    "",
                    message.content
                ).strip()

                # メンションだけならAPIを呼ばない
                if clean_text:

                    allowed = (
                        await self.bot.db.check_daily_limit(
                            str(message.author.id)
                        )
                    )

                    if not allowed:

                        await message.reply(
                            "今日の会話回数は終わりや。"
                            "また明日な！"
                        )

                    else:

                        # ======================================================
                        # ★ 過去会話取得
                        # ======================================================

                        history = (
                            await self.bot.db
                            .get_conversation_history(
                                guild_id=message.guild.id,
                                channel_id=message.channel.id,
                                user_id=message.author.id,
                                limit=Config.MEMORY_MESSAGE_LIMIT
                            )
                        )

                        async with message.channel.typing():

                            (
                                reply,
                                selected_model,
                                route
                            ) = await self.bot.ai.chat(
                                user_name=(
                                    message.author.display_name
                                ),
                                content=clean_text,
                                history=history
                            )

                        if (
                            not reply
                            or not reply.strip()
                        ):

                            reply = Config.EMPTY_MSG

                        # ======================================================
                        # 正常応答のみ会話履歴へ保存
                        # ======================================================

                        error_responses = {
                            Config.ERROR_MSG,
                            Config.TIMEOUT_MSG,
                            Config.EMPTY_MSG,
                        }

                        if reply not in error_responses:

                            await self.bot.db.add_conversation_message(
                                guild_id=message.guild.id,
                                channel_id=message.channel.id,
                                user_id=message.author.id,
                                role="user",
                                content=clean_text
                            )

                            await self.bot.db.add_conversation_message(
                                guild_id=message.guild.id,
                                channel_id=message.channel.id,
                                user_id=message.author.id,
                                role="assistant",
                                content=reply
                            )

                        logger.info(
                            "AI response | "
                            f"user={message.author.id} | "
                            f"model={selected_model} | "
                            f"route={route}"
                        )

                        if len(reply) > 1900:

                            file = discord.File(
                                io.BytesIO(
                                    reply.encode()
                                ),
                                filename="reply.txt"
                            )

                            await message.reply(
                                "長くなったから"
                                "ファイルにしたで！",
                                file=file
                            )

                        else:

                            await message.reply(
                                reply
                            )

        except Exception as e:

            logger.exception(
                f"AI chat processing failed: {e}"
            )

        # ----------------------------------------------------------------------
        # XP
        # ----------------------------------------------------------------------

        try:

            leveled_up = (
                await self.bot.db.add_xp(
                    message.author.id,
                    10
                )
            )

            if leveled_up:

                level, _ = (
                    await self.bot.db.get_user_data(
                        message.author.id
                    )
                )

                rewards = (
                    await self.bot.db._fetchall(
                        """
                        SELECT role_id
                        FROM level_rewards
                        WHERE guild_id=?
                        AND level<=?
                        """,
                        (
                            message.guild.id,
                            level
                        )
                    )
                )

                for (role_id,) in rewards:

                    role = message.guild.get_role(
                        role_id
                    )

                    if role:

                        try:

                            await message.author.add_roles(
                                role
                            )

                        except discord.Forbidden:

                            logger.warning(
                                "Level reward "
                                "permission denied."
                            )

                await message.channel.send(
                    f"🎉 {message.author.mention} "
                    f"レベルアップ！ "
                    f"(Lv.{level})"
                )

        except Exception as e:

            logger.exception(
                f"XP processing failed: {e}"
            )

    # ==========================================================================
    # Reaction Add
    # ==========================================================================

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent
    ):

        if (
            payload.member
            and payload.member.bot
        ):
            return

        # Reaction Role

        try:

            row = await self.bot.db._fetchone(
                """
                SELECT role_id
                FROM reaction_roles
                WHERE message_id=?
                AND emoji=?
                """,
                (
                    payload.message_id,
                    str(payload.emoji)
                )
            )

            if row and payload.member:

                role = payload.member.guild.get_role(
                    row[0]
                )

                if role:

                    await payload.member.add_roles(
                        role
                    )

        except Exception as e:

            logger.exception(
                f"Reaction role add failed: {e}"
            )

        # Translation

        if (
            str(payload.emoji)
            in Config.FLAG_MAP
        ):

            try:

                channel = self.bot.get_channel(
                    payload.channel_id
                )

                if not channel:
                    return

                message = await channel.fetch_message(
                    payload.message_id
                )

                if not message.content:
                    return

                language = Config.FLAG_MAP[
                    str(payload.emoji)
                ]

                translated = (
                    await self.bot.ai.translate(
                        message.content,
                        language
                    )
                )

                if not translated or not translated.strip():
                    translated = Config.ERROR_MSG

                if not payload.member:
                    return

                if len(translated) > 4000:

                    file = discord.File(
                        io.BytesIO(
                            translated.encode()
                        ),
                        filename="trans.txt"
                    )

                    await payload.member.send(
                        "長すぎるから"
                        "ファイルにするな！",
                        file=file
                    )

                else:

                    embed = discord.Embed(
                        title=(
                            f"🌐 翻訳 ({language})"
                        ),
                        description=translated,
                        color=discord.Color.blue()
                    )

                    preview = (
                        message.content[:50] + "..."
                        if len(message.content) > 50
                        else message.content
                    )

                    embed.set_footer(
                        text=f"原文: {preview}"
                    )

                    await payload.member.send(
                        embed=embed
                    )

            except discord.Forbidden:

                logger.info(
                    "Translation DM blocked "
                    f"(user={payload.user_id})"
                )

            except Exception as e:

                logger.exception(
                    f"Translation reaction failed: {e}"
                )

        # Starboard

        if str(payload.emoji) == "❤️":

            try:

                channel = self.bot.get_channel(
                    payload.channel_id
                )

                if not channel:
                    return

                message = await channel.fetch_message(
                    payload.message_id
                )

                reaction = discord.utils.get(
                    message.reactions,
                    emoji="❤️"
                )

                if (
                    not reaction
                    or reaction.count < 10
                ):
                    return

                posted = (
                    await self.bot.db._fetchone(
                        """
                        SELECT message_id
                        FROM starboard_log
                        WHERE message_id=?
                        """,
                        (
                            message.id,
                        )
                    )
                )

                if posted:
                    return

                starboard_id = (
                    await self.bot.db.get_config(
                        payload.guild_id,
                        "starboard_ch"
                    )
                )

                if not starboard_id:
                    return

                starboard = self.bot.get_channel(
                    starboard_id
                )

                if not starboard:
                    return

                embed = discord.Embed(
                    description=message.content,
                    color=discord.Color.red(),
                    timestamp=message.created_at
                )

                embed.set_author(
                    name=message.author.display_name,
                    icon_url=(
                        message.author
                        .display_avatar.url
                    )
                )

                embed.add_field(
                    name="Original",
                    value=(
                        f"[Jump]"
                        f"({message.jump_url})"
                    )
                )

                if message.attachments:

                    embed.set_image(
                        url=message.attachments[0].url
                    )

                await starboard.send(
                    "いいねがたくさん。"
                    "殿堂入りやね！（茜）",
                    embed=embed
                )

                await self.bot.db._execute(
                    """
                    INSERT INTO starboard_log
                    (message_id)
                    VALUES (?)
                    """,
                    (
                        message.id,
                    )
                )

            except Exception as e:

                logger.exception(
                    f"Starboard processing failed: {e}"
                )

    # ==========================================================================
    # Reaction Remove
    # ==========================================================================

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self,
        payload: discord.RawReactionActionEvent
    ):

        try:

            row = await self.bot.db._fetchone(
                """
                SELECT role_id
                FROM reaction_roles
                WHERE message_id=?
                AND emoji=?
                """,
                (
                    payload.message_id,
                    str(payload.emoji)
                )
            )

            if not row:
                return

            guild = self.bot.get_guild(
                payload.guild_id
            )

            if not guild:
                return

            member = guild.get_member(
                payload.user_id
            )

            role = guild.get_role(
                row[0]
            )

            if member and role:

                await member.remove_roles(
                    role
                )

        except Exception as e:

            logger.exception(
                f"Reaction role remove failed: {e}"
            )

    # ==========================================================================
    # Deleted Message
    # ==========================================================================

    @commands.Cog.listener()
    async def on_message_delete(
        self,
        message: discord.Message
    ):

        if (
            message.author.bot
            or not message.guild
        ):
            return

        try:

            log_id = await self.bot.db.get_config(
                message.guild.id,
                "log_ch"
            )

            if not log_id:
                return

            channel = message.guild.get_channel(
                log_id
            )

            if not channel:
                return

            embed = discord.Embed(
                title="🗑️ 削除ログ",
                description=(
                    message.content
                    or "(本文なし)"
                ),
                color=discord.Color.red()
            )

            embed.set_author(
                name=message.author.display_name,
                icon_url=(
                    message.author
                    .display_avatar.url
                )
            )

            embed.add_field(
                name="場所",
                value=message.channel.mention
            )

            await channel.send(
                embed=embed
            )

        except Exception as e:

            logger.exception(
                f"Delete logging failed: {e}"
            )

    # ==========================================================================
    # Voice
    # ==========================================================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member,
        before,
        after
    ):

        if before.channel == after.channel:
            return

        try:

            log_id = await self.bot.db.get_config(
                member.guild.id,
                "log_ch"
            )

            if not log_id:
                return

            channel = member.guild.get_channel(
                log_id
            )

            if not channel:
                return

            if not before.channel:

                description = (
                    f"📥 参加: {after.channel.name}"
                )

            elif not after.channel:

                description = (
                    f"📤 退出: {before.channel.name}"
                )

            else:

                description = (
                    f"➡️ 移動: "
                    f"{before.channel.name} "
                    f"-> {after.channel.name}"
                )

            await channel.send(
                embed=discord.Embed(
                    description=(
                        f"{member.mention} "
                        f"{description}"
                    ),
                    color=discord.Color.green()
                )
            )

        except Exception as e:

            logger.exception(
                f"Voice logging failed: {e}"
            )

    # ==========================================================================
    # Welcome
    # ==========================================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member
    ):

        try:

            welcome_id = (
                await self.bot.db.get_config(
                    member.guild.id,
                    "welcome_ch"
                )
            )

            if not welcome_id:
                return

            channel = member.guild.get_channel(
                welcome_id
            )

            if channel:

                await channel.send(
                    f"{member.mention} "
                    "表現の自由界隈サーバーへようこそ。"
                    "このサーバーのマスコットキャラクターの"
                    "表自派茜（ひょうじは あかね）やで！ "
                    "ゆっくりしていってな！"
                )

        except Exception as e:

            logger.exception(
                f"Welcome message failed: {e}"
            )


async def setup(bot):

    await bot.add_cog(
        EventsCog(bot)
    )
