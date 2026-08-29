import io
import logging
import re

from collections import defaultdict, deque
from datetime import datetime, time, timedelta

import discord
from discord.ext import commands, tasks

from config import Config, JST


logger = logging.getLogger(
    "AkaneBot"
)


class EventsCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        self.spam_check = defaultdict(
            lambda: deque(
                maxlen=(
                    Config.SPAM_MESSAGE_THRESHOLD
                )
            )
        )

        self.duplicate_check = defaultdict(
            lambda: deque(
                maxlen=(
                    Config.DUPLICATE_MESSAGE_THRESHOLD
                )
            )
        )

        self.spam_strikes = {}

        self.xp_last_award = {}

    # ==========================================================================
    # Lifecycle
    # ==========================================================================

    async def cog_load(
        self
    ):

        self.loop_reminders.start()
        self.loop_monthly.start()
        self.loop_memory_cleanup.start()

        logger.info(
            "EventsCog background tasks started."
        )

    def cog_unload(
        self
    ):

        self.loop_reminders.cancel()
        self.loop_monthly.cancel()
        self.loop_memory_cleanup.cancel()

    # ==========================================================================
    # Unlock Notification
    # ==========================================================================

    async def send_unlock_notifications(
        self,
        channel,
        member,
        unlocks: dict
    ):

        if not Config.ACHIEVEMENT_NOTIFICATIONS:

            return

        lines = []

        for key in unlocks.get(
            "achievements",
            []
        ):

            data = Config.ACHIEVEMENTS.get(
                key
            )

            if data:

                lines.append(
                    f"🏆 **実績解除！** "
                    f"{data['emoji']} "
                    f"**{data['name']}**\n"
                    f"└ {data['description']}"
                )

        for key in unlocks.get(
            "titles",
            []
        ):

            data = Config.TITLES.get(
                key
            )

            if data:

                lines.append(
                    f"🎖️ **称号獲得！** "
                    f"**{data['name']}**\n"
                    f"└ {data['description']}"
                )

        if not lines:

            return

        try:

            await channel.send(
                content=member.mention,
                embed=discord.Embed(
                    title="🎉 新しい解除項目があるで！",
                    description="\n\n".join(
                        lines
                    ),
                    color=discord.Color.gold()
                )
            )

        except Exception as e:

            logger.exception(
                f"Unlock notification failed: {e}"
            )

    # ==========================================================================
    # Spam
    # ==========================================================================

    async def handle_spam(
        self,
        message: discord.Message,
        reason: str
    ):

        if (
            not isinstance(
                message.author,
                discord.Member
            )
            or message.author.guild_permissions.administrator
        ):

            return

        key = (
            message.guild.id,
            message.author.id
        )

        now_timestamp = datetime.now().timestamp()

        strike_data = self.spam_strikes.get(
            key
        )

        if (
            not strike_data
            or now_timestamp
            - strike_data["last"]
            > Config.SPAM_STRIKE_RESET_SECONDS
        ):

            strike = 1

        else:

            strike = (
                strike_data["count"]
                + 1
            )

        self.spam_strikes[
            key
        ] = {
            "count": strike,
            "last": now_timestamp,
        }

        if strike == 1:

            try:

                await message.channel.send(
                    f"⚠️ {message.author.mention} "
                    "連投っぽいで。"
                    "少しゆっくり頼むわ！",
                    delete_after=10
                )

            except Exception:

                pass

            return

        if strike == 2:

            timeout_seconds = (
                Config.SPAM_TIMEOUT_1_SECONDS
            )

        elif strike == 3:

            timeout_seconds = (
                Config.SPAM_TIMEOUT_2_SECONDS
            )

        else:

            timeout_seconds = (
                Config.SPAM_TIMEOUT_3_SECONDS
            )

        try:

            await message.author.timeout(
                timedelta(
                    seconds=timeout_seconds
                ),
                reason=(
                    "Akane Bot Spam Protection | "
                    f"Strike {strike} | "
                    f"{reason}"
                )
            )

            await message.channel.send(
                f"🛡️ {message.author.mention} "
                f"**{timeout_seconds}秒** "
                "Timeoutしたで。"
            )

        except Exception as e:

            logger.exception(
                f"Spam timeout failed: {e}"
            )

    # ==========================================================================
    # Reminder
    # ==========================================================================

    @tasks.loop(
        seconds=60
    )
    async def loop_reminders(
        self
    ):

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

                if channel:

                    try:

                        await channel.send(
                            f"⏰ <@{user_id}> "
                            f"リマインダー: "
                            f"{reminder_message}"
                        )

                    except Exception as e:

                        logger.exception(
                            f"Reminder send failed: {e}"
                        )

        except Exception as e:

            logger.exception(
                f"Reminder loop failed: {e}"
            )

    @loop_reminders.before_loop
    async def before_loop_reminders(
        self
    ):

        await self.bot.wait_until_ready()

    # ==========================================================================
    # Monthly
    # ==========================================================================

    @tasks.loop(
        time=time(
            hour=7,
            minute=0,
            tzinfo=JST
        )
    )
    async def loop_monthly(
        self
    ):

        if datetime.now(
            JST
        ).day != 1:

            return

        try:

            rows = await self.bot.db._fetchall(
                """
                SELECT
                    rule_ch,
                    target_ch
                FROM monthly_rules
                """
            )

            for (
                rule_id,
                target_id
            ) in rows:

                channel = self.bot.get_channel(
                    target_id
                )

                if channel:

                    await channel.send(
                        "表現の自由界隈のみなさん、"
                        "おはよーさん！☀️ "
                        "新しい一ヶ月が始まったで〜！🚀\n"
                        f"📌 **ルールブック:** "
                        f"<#{rule_id}>\n"
                        "目を通しておいてな！"
                    )

        except Exception as e:

            logger.exception(
                f"Monthly loop failed: {e}"
            )

    @loop_monthly.before_loop
    async def before_loop_monthly(
        self
    ):

        await self.bot.wait_until_ready()

    # ==========================================================================
    # Memory Cleanup
    # ==========================================================================

    @tasks.loop(
        time=time(
            hour=4,
            minute=0,
            tzinfo=JST
        )
    )
    async def loop_memory_cleanup(
        self
    ):

        try:

            deleted = await self.bot.db.cleanup_old_conversations(
                Config.MEMORY_RETENTION_DAYS
            )

            if deleted:

                logger.info(
                    f"Memory cleanup: {deleted}"
                )

        except Exception as e:

            logger.exception(
                f"Memory cleanup failed: {e}"
            )

    @loop_memory_cleanup.before_loop
    async def before_memory_cleanup(
        self
    ):

        await self.bot.wait_until_ready()

    # ==========================================================================
    # Message
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

        # ======================================================================
        # Spam
        # ======================================================================

        if not message.author.guild_permissions.administrator:

            key = (
                message.guild.id,
                message.author.id
            )

            now_timestamp = datetime.now().timestamp()

            history = self.spam_check[
                key
            ]

            history.append(
                now_timestamp
            )

            burst_spam = (
                len(history)
                >= Config.SPAM_MESSAGE_THRESHOLD
                and (
                    history[-1]
                    - history[0]
                    <= Config.SPAM_WINDOW_SECONDS
                )
            )

            normalized = (
                message.content
                .strip()
                .lower()
            )

            duplicate_history = self.duplicate_check[
                key
            ]

            if normalized:

                duplicate_history.append(
                    normalized
                )

            duplicate_spam = (
                bool(normalized)
                and len(duplicate_history)
                >= Config.DUPLICATE_MESSAGE_THRESHOLD
                and len(
                    set(
                        duplicate_history
                    )
                )
                == 1
            )

            mass_mention = (
                len(
                    {
                        member.id
                        for member
                        in message.mentions
                    }
                )
                >= Config.MASS_MENTION_THRESHOLD
            )

            reason = None

            if mass_mention:
                reason = "大量メンション"
            elif duplicate_spam:
                reason = "同じ文章の連投"
            elif burst_spam:
                reason = "短時間の大量投稿"

            if reason:

                await self.handle_spam(
                    message,
                    reason
                )

                return

        # ======================================================================
        # NG Word
        # ======================================================================

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

            for (
                word,
            ) in ng_words:

                if word in message.content:

                    await message.delete()

                    await message.channel.send(
                        f"{message.author.mention} "
                        "NGワードやで！",
                        delete_after=3
                    )

                    return

        except Exception as e:

            logger.exception(
                f"NG word processing failed: {e}"
            )

        # ======================================================================
        # Stats
        # ======================================================================

        try:

            await self.bot.db.increment_message_count(
                message.guild.id,
                message.author.id
            )

            unlocks = await self.bot.db.evaluate_progress_unlocks(
                message.guild.id,
                message.author.id
            )

            await self.send_unlock_notifications(
                message.channel,
                message.author,
                unlocks
            )

        except Exception as e:

            logger.exception(
                f"Stats failed: {e}"
            )

        # ======================================================================
        # Auto Reply
        # ======================================================================

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

        # ======================================================================
        # AI
        # ======================================================================

        try:

            auto_chat_channel = await self.bot.db.get_config(
                message.guild.id,
                "auto_chat_ch"
            )

            is_target = (
                self.bot.user
                in message.mentions
                or (
                    auto_chat_channel is not None
                    and message.channel.id
                    == auto_chat_channel
                )
            )

            if is_target:

                clean_text = re.sub(
                    r"<@!?\d+>",
                    "",
                    message.content
                ).strip()

                if clean_text:

                    allowed = await self.bot.db.check_daily_limit(
                        str(
                            message.author.id
                        )
                    )

                    if not allowed:

                        await message.reply(
                            "今日の会話回数は終わりや。"
                            "また明日な！"
                        )

                    else:

                        conversation_history = (
                            await self.bot.db
                            .get_conversation_history(
                                message.guild.id,
                                message.channel.id,
                                message.author.id,
                                Config.MEMORY_MESSAGE_LIMIT
                            )
                        )

                        async with message.channel.typing():

                            (
                                reply,
                                selected_model,
                                route
                            ) = await self.bot.ai.chat(
                                user_name=(
                                    message.author
                                    .display_name
                                ),
                                content=clean_text,
                                history=conversation_history
                            )

                        if (
                            not reply
                            or not reply.strip()
                        ):

                            reply = Config.EMPTY_MSG

                        errors = {
                            Config.ERROR_MSG,
                            Config.TIMEOUT_MSG,
                            Config.EMPTY_MSG,
                        }

                        if reply not in errors:

                            await self.bot.db.add_conversation_message(
                                message.guild.id,
                                message.channel.id,
                                message.author.id,
                                "user",
                                clean_text
                            )

                            await self.bot.db.add_conversation_message(
                                message.guild.id,
                                message.channel.id,
                                message.author.id,
                                "assistant",
                                reply
                            )

                            await self.bot.db.increment_ai_chat_count(
                                message.guild.id,
                                message.author.id
                            )

                            unlocks = (
                                await self.bot.db
                                .evaluate_progress_unlocks(
                                    message.guild.id,
                                    message.author.id
                                )
                            )

                            await self.send_unlock_notifications(
                                message.channel,
                                message.author,
                                unlocks
                            )

                        logger.info(
                            "AI response | "
                            f"user={message.author.id} | "
                            f"model={selected_model} | "
                            f"route={route}"
                        )

                        if len(reply) > 1900:

                            await message.reply(
                                "長くなったから"
                                "ファイルにしたで！",
                                file=discord.File(
                                    io.BytesIO(
                                        reply.encode(
                                            "utf-8"
                                        )
                                    ),
                                    filename="reply.txt"
                                )
                            )

                        else:

                            await message.reply(
                                reply
                            )

        except Exception as e:

            logger.exception(
                f"AI processing failed: {e}"
            )

        # ======================================================================
        # XP + V33 Weekly XP
        # ======================================================================

        try:

            user_id = (
                message.author.id
            )

            now_timestamp = datetime.now().timestamp()

            last_award = self.xp_last_award.get(
                (
                    message.guild.id,
                    user_id
                )
            )

            can_gain_xp = (
                last_award is None
                or (
                    now_timestamp
                    - last_award
                    >= Config.XP_COOLDOWN_SECONDS
                )
            )

            if can_gain_xp:

                (
                    leveled_up,
                    level_value,
                    current_xp
                ) = await self.bot.db.add_xp(
                    user_id,
                    Config.XP_PER_MESSAGE
                )

                # V33
                weekly_xp = await self.bot.db.add_weekly_xp(
                    message.guild.id,
                    user_id,
                    Config.XP_PER_MESSAGE
                )

                self.xp_last_award[
                    (
                        message.guild.id,
                        user_id
                    )
                ] = now_timestamp

                logger.debug(
                    "XP awarded | "
                    f"guild={message.guild.id} | "
                    f"user={user_id} | "
                    f"weekly={weekly_xp}"
                )

                unlocks = await self.bot.db.evaluate_progress_unlocks(
                    message.guild.id,
                    user_id
                )

                await self.send_unlock_notifications(
                    message.channel,
                    message.author,
                    unlocks
                )

                if leveled_up:

                    rewards = await self.bot.db._fetchall(
                        """
                        SELECT role_id
                        FROM level_rewards
                        WHERE guild_id=?
                        AND level<=?
                        """,
                        (
                            message.guild.id,
                            level_value
                        )
                    )

                    for (
                        role_id,
                    ) in rewards:

                        role = message.guild.get_role(
                            role_id
                        )

                        if (
                            not role
                            or role
                            in message.author.roles
                        ):

                            continue

                        try:

                            await message.author.add_roles(
                                role,
                                reason=(
                                    "Akane Bot "
                                    "level reward"
                                )
                            )

                        except Exception as e:

                            logger.exception(
                                f"Role reward failed: {e}"
                            )

                    required_next = self.bot.db.required_xp(
                        level_value
                    )

                    await message.channel.send(
                        f"🎉 {message.author.mention} "
                        f"レベルアップ！ "
                        f"**Lv.{level_value}** やで！\n"
                        f"現在XP: "
                        f"**{current_xp} / "
                        f"{required_next}**"
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
                    str(
                        payload.emoji
                    )
                )
            )

            if (
                row
                and payload.member
            ):

                role = payload.member.guild.get_role(
                    row[0]
                )

                if role:

                    await payload.member.add_roles(
                        role
                    )

        except Exception as e:

            logger.exception(
                f"Reaction role failed: {e}"
            )

        # ----------------------------------------------------------------------
        # Translation
        # ----------------------------------------------------------------------

        if (
            str(
                payload.emoji
            )
            in Config.FLAG_MAP
        ):

            try:

                channel = self.bot.get_channel(
                    payload.channel_id
                )

                if not channel:

                    return

                source = await channel.fetch_message(
                    payload.message_id
                )

                if (
                    not source.content
                    or not payload.member
                ):

                    return

                language = Config.FLAG_MAP[
                    str(
                        payload.emoji
                    )
                ]

                translated = await self.bot.ai.translate(
                    source.content,
                    language
                )

                if len(translated) > 4000:

                    await payload.member.send(
                        file=discord.File(
                            io.BytesIO(
                                translated.encode(
                                    "utf-8"
                                )
                            ),
                            filename="trans.txt"
                        )
                    )

                else:

                    await payload.member.send(
                        embed=discord.Embed(
                            title=(
                                f"🌐 翻訳 "
                                f"({language})"
                            ),
                            description=translated,
                            color=discord.Color.blue()
                        )
                    )

            except Exception as e:

                logger.exception(
                    f"Translation failed: {e}"
                )

        # ----------------------------------------------------------------------
        # Starboard
        # ----------------------------------------------------------------------

        if str(
            payload.emoji
        ) == "❤️":

            try:

                channel = self.bot.get_channel(
                    payload.channel_id
                )

                if not channel:

                    return

                source = await channel.fetch_message(
                    payload.message_id
                )

                reaction = discord.utils.get(
                    source.reactions,
                    emoji="❤️"
                )

                if (
                    not reaction
                    or reaction.count < 10
                ):

                    return

                posted = await self.bot.db._fetchone(
                    """
                    SELECT message_id
                    FROM starboard_log
                    WHERE message_id=?
                    """,
                    (
                        source.id,
                    )
                )

                if posted:

                    return

                starboard_id = await self.bot.db.get_config(
                    payload.guild_id,
                    "starboard_ch"
                )

                starboard = self.bot.get_channel(
                    starboard_id
                )

                if not starboard:

                    return

                embed = discord.Embed(
                    description=(
                        source.content
                        or "(本文なし)"
                    ),
                    color=discord.Color.red(),
                    timestamp=source.created_at
                )

                embed.set_author(
                    name=source.author.display_name,
                    icon_url=(
                        source.author
                        .display_avatar.url
                    )
                )

                embed.add_field(
                    name="Original",
                    value=(
                        f"[Jump]"
                        f"({source.jump_url})"
                    )
                )

                if source.attachments:

                    embed.set_image(
                        url=source.attachments[0].url
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
                        source.id,
                    )
                )

            except Exception as e:

                logger.exception(
                    f"Starboard failed: {e}"
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
                    str(
                        payload.emoji
                    )
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

            if (
                member
                and role
            ):

                await member.remove_roles(
                    role
                )

        except Exception as e:

            logger.exception(
                f"Reaction remove failed: {e}"
            )

    # ==========================================================================
    # Message Delete
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

            channel = (
                message.guild.get_channel(
                    log_id
                )
                if log_id
                else None
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
                f"Delete log failed: {e}"
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

            channel = (
                member.guild.get_channel(
                    log_id
                )
                if log_id
                else None
            )

            if not channel:

                return

            if not before.channel:

                text = (
                    f"📥 参加: "
                    f"{after.channel.name}"
                )

            elif not after.channel:

                text = (
                    f"📤 退出: "
                    f"{before.channel.name}"
                )

            else:

                text = (
                    f"➡️ 移動: "
                    f"{before.channel.name} "
                    f"→ "
                    f"{after.channel.name}"
                )

            await channel.send(
                f"{member.mention} {text}"
            )

        except Exception as e:

            logger.exception(
                f"Voice log failed: {e}"
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

            welcome_id = await self.bot.db.get_config(
                member.guild.id,
                "welcome_ch"
            )

            channel = (
                member.guild.get_channel(
                    welcome_id
                )
                if welcome_id
                else None
            )

            if channel:

                await channel.send(
                    f"{member.mention} "
                    "表現の自由界隈サーバーへようこそ。"
                    "表自派茜やで！ "
                    "ゆっくりしていってな！"
                )

        except Exception as e:

            logger.exception(
                f"Welcome failed: {e}"
            )

    # ==========================================================================
    # Ticket Manual Delete
    # ==========================================================================

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self,
        channel
    ):

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            return

        try:

            ticket = await self.bot.db.get_ticket_by_channel(
                channel.id
            )

            if (
                ticket
                and ticket[4] == "open"
            ):

                await self.bot.db.close_ticket(
                    channel.id
                )

        except Exception as e:

            logger.exception(
                f"Ticket cleanup failed: {e}"
            )


# ==============================================================================
# Setup
# ==============================================================================

async def setup(
    bot
):

    await bot.add_cog(
        EventsCog(
            bot
        )
    )
