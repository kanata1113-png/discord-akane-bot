import hashlib
import io
import logging
import random

from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz

from discord import app_commands
from discord.ext import commands

from config import Config, JST
from views.event_view import EventView


logger = logging.getLogger(
    "AkaneBot"
)


class GeneralCog(commands.Cog):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

    # ==========================================================================
    # Helpers
    # ==========================================================================

    async def _send_unlock_notifications(
        self,
        interaction: discord.Interaction,
        unlocks: dict
    ):

        if not Config.ACHIEVEMENT_NOTIFICATIONS:

            return

        achievement_keys = unlocks.get(
            "achievements",
            []
        )

        title_keys = unlocks.get(
            "titles",
            []
        )

        if (
            not achievement_keys
            and not title_keys
        ):

            return

        lines = []

        for key in achievement_keys:

            data = Config.ACHIEVEMENTS.get(
                key
            )

            if data:

                lines.append(
                    f"🏆 実績解除: "
                    f"**{data['emoji']} "
                    f"{data['name']}**"
                )

        for key in title_keys:

            data = Config.TITLES.get(
                key
            )

            if data:

                lines.append(
                    f"🎖️ 称号獲得: "
                    f"**{data['name']}**"
                )

        if not lines:

            return

        try:

            await interaction.followup.send(
                "\n".join(
                    lines
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                "Unlock notification failed | "
                f"error={e}"
            )

    @staticmethod
    def _ranking_medal(
        position: int
    ) -> str:

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }

        return medals.get(
            position,
            f"`{position}.`"
        )

    def _member_name(
        self,
        guild: discord.Guild,
        user_id: int
    ) -> str:

        member = guild.get_member(
            int(
                user_id
            )
        )

        if member:

            return member.display_name

        return f"User {user_id}"

    # ==========================================================================
    # Translate
    # ==========================================================================

    @app_commands.command(
        name="translate",
        description="AI翻訳"
    )
    async def translate(
        self,
        interaction: discord.Interaction,
        language: str,
        text: str
    ):

        await interaction.response.defer()

        try:

            result = await self.bot.ai.translate(
                text,
                language
            )

            if (
                not result
                or not result.strip()
            ):

                result = Config.ERROR_MSG

            if len(result) > 4000:

                file = discord.File(
                    io.BytesIO(
                        result.encode(
                            "utf-8"
                        )
                    ),
                    filename="trans.txt"
                )

                await interaction.followup.send(
                    "長すぎるから"
                    "ファイルにするな！",
                    file=file
                )

            else:

                await interaction.followup.send(
                    embed=discord.Embed(
                        title=(
                            f"翻訳 "
                            f"({language})"
                        ),
                        description=result,
                        color=discord.Color.blue()
                    )
                )

        except Exception as e:

            logger.exception(
                f"/translate failed: {e}"
            )

            await interaction.followup.send(
                "翻訳中にエラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Define
    # ==========================================================================

    @app_commands.command(
        name="define",
        description="AI辞書"
    )
    async def define(
        self,
        interaction: discord.Interaction,
        word: str,
        wiki_mode: bool = False
    ):

        await interaction.response.defer()

        try:

            result = await self.bot.ai.define_word(
                word,
                wiki_mode
            )

            if (
                not result
                or not result.strip()
            ):

                await interaction.followup.send(
                    Config.ERROR_MSG,
                    ephemeral=True
                )

                return

            if len(result) > 4000:

                file = discord.File(
                    io.BytesIO(
                        result.encode(
                            "utf-8"
                        )
                    ),
                    filename="define.txt"
                )

                await interaction.followup.send(
                    "長すぎるから"
                    "ファイルにするな！",
                    file=file
                )

                return

            title = (
                f"📖 辞書: {word}"
                + (
                    " (Wiki Mode)"
                    if wiki_mode
                    else ""
                )
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title=title,
                    description=result,
                    color=discord.Color.green()
                )
            )

        except Exception as e:

            logger.exception(
                f"/define failed: {e}"
            )

            await interaction.followup.send(
                "辞書処理中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Summary
    # ==========================================================================

    @app_commands.command(
        name="summary",
        description="自分の発言要約"
    )
    async def summary(
        self,
        interaction: discord.Interaction,
        back: int
    ):

        back = max(
            1,
            min(
                back,
                20
            )
        )

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            messages = [
                message.content
                async for message
                in interaction.channel.history(
                    limit=100
                )
                if message.author
                == interaction.user
            ][:back]

            if not messages:

                await interaction.followup.send(
                    "発言が見つからんかったわ。",
                    ephemeral=True
                )

                return

            messages.reverse()

            result = await self.bot.ai.summarize(
                messages
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="📝 発言要約",
                    description=(
                        result
                        or Config.ERROR_MSG
                    ),
                    color=discord.Color.orange()
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/summary failed: {e}"
            )

            await interaction.followup.send(
                "要約中にエラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Event
    # ==========================================================================

    @app_commands.command(
        name="event",
        description="イベント作成"
    )
    async def event(
        self,
        interaction: discord.Interaction,
        title: str,
        date: str,
        time: str
    ):

        try:

            naive = datetime.strptime(
                f"{date} {time}",
                "%Y/%m/%d %H:%M"
            )

            event_datetime = JST.localize(
                naive
            )

        except ValueError:

            await interaction.response.send_message(
                "日時は "
                "`YYYY/MM/DD HH:MM` "
                "の形式で頼むで！",
                ephemeral=True
            )

            return

        timestamp = int(
            event_datetime.timestamp()
        )

        embed = discord.Embed(
            title=f"📅 {title}",
            description=(
                f"日時: <t:{timestamp}:F>"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="【参加】",
            value="なし"
        )

        embed.add_field(
            name="【不参加】",
            value="なし"
        )

        await interaction.response.send_message(
            embed=embed,
            view=EventView()
        )

        try:

            await interaction.guild.create_scheduled_event(
                name=title,
                start_time=event_datetime,
                end_time=(
                    event_datetime
                    + timedelta(
                        hours=2
                    )
                ),
                location="Discord",
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only
            )

        except Exception as e:

            logger.exception(
                f"Scheduled event failed: {e}"
            )

    # ==========================================================================
    # Poll
    # ==========================================================================

    @app_commands.command(
        name="poll",
        description="投票作成"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None
    ):

        options = [
            option
            for option
            in [
                option1,
                option2,
                option3,
                option4,
            ]
            if option
        ]

        emojis = [
            "1️⃣",
            "2️⃣",
            "3️⃣",
            "4️⃣",
        ]

        description = "\n".join(
            f"{emojis[index]} {option}"
            for index, option
            in enumerate(
                options
            )
        )

        await interaction.response.send_message(
            f"📊 **{question}** #投票",
            embed=discord.Embed(
                description=description,
                color=discord.Color.gold()
            )
        )

        message = await interaction.original_response()

        for index in range(
            len(options)
        ):

            await message.add_reaction(
                emojis[index]
            )

    # ==========================================================================
    # Search
    # ==========================================================================

    @app_commands.command(
        name="search",
        description="メッセージ検索"
    )
    async def search(
        self,
        interaction: discord.Interaction,
        keyword: str,
        target_channel: Optional[
            discord.TextChannel
        ] = None,
        member: Optional[
            discord.Member
        ] = None,
        days: Optional[int] = None
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        channel = (
            target_channel
            or interaction.channel
        )

        after = (
            datetime.now(
                pytz.utc
            )
            - timedelta(
                days=days
            )
            if days
            else None
        )

        found = []

        try:

            async for message in channel.history(
                limit=1000,
                after=after
            ):

                if (
                    member
                    and message.author != member
                ):

                    continue

                if keyword in message.content:

                    found.append(
                        message
                    )

                    if len(found) >= 100:

                        break

        except Exception as e:

            logger.exception(
                f"/search failed: {e}"
            )

            await interaction.followup.send(
                "検索中にエラーが起きたで。",
                ephemeral=True
            )

            return

        if not found:

            await interaction.followup.send(
                "見つからへんかったで。",
                ephemeral=True
            )

            return

        if len(found) > 20:

            text = "\n".join(
                (
                    f"[{message.created_at}] "
                    f"{message.author}: "
                    f"{message.content}"
                )
                for message in found
            )

            file = discord.File(
                io.BytesIO(
                    text.encode(
                        "utf-8"
                    )
                ),
                filename="result.txt"
            )

            await interaction.followup.send(
                f"{len(found)}件",
                file=file,
                ephemeral=True
            )

        else:

            description = "\n".join(
                (
                    f"• "
                    f"[{message.content[:30]}]"
                    f"({message.jump_url})"
                )
                for message in found
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title=(
                        f"検索: {keyword}"
                    ),
                    description=description
                ),
                ephemeral=True
            )

    # ==========================================================================
    # Level
    # ==========================================================================

    @app_commands.command(
        name="level",
        description="レベル確認"
    )
    async def level(
        self,
        interaction: discord.Interaction
    ):

        try:

            info = await self.bot.db.get_level_info(
                interaction.user.id
            )

            await interaction.response.send_message(
                (
                    f"📊 **Lv.{info['level']}**\n"
                    f"✨ XP: "
                    f"**{info['xp']} / "
                    f"{info['required_xp']}**\n"
                    f"🎯 次まであと "
                    f"**{info['remaining_xp']} XP**"
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/level failed: {e}"
            )

            await interaction.response.send_message(
                "レベル情報を取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Legacy Leaderboard
    # ==========================================================================

    @app_commands.command(
        name="leaderboard",
        description="レベルランキング TOP30"
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            rows = await self.bot.db.get_leaderboard(
                30
            )

            lines = []

            for index, (
                user_id,
                level_value,
                xp
            ) in enumerate(
                rows,
                1
            ):

                member = interaction.guild.get_member(
                    int(
                        user_id
                    )
                )

                if not member:

                    continue

                lines.append(
                    f"{index}. "
                    f"{member.display_name} "
                    f"(Lv.{level_value} / XP {xp})"
                )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="🏆 レベルランキング",
                    description=(
                        "\n".join(
                            lines
                        )
                        or "データなし"
                    ),
                    color=discord.Color.gold()
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/leaderboard failed: {e}"
            )

            await interaction.followup.send(
                "ランキング取得中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Reminder
    # ==========================================================================

    @app_commands.command(
        name="remind",
        description="リマインダー"
    )
    async def remind(
        self,
        interaction: discord.Interaction,
        minutes: int,
        message: str
    ):

        if minutes < 1:

            await interaction.response.send_message(
                "1分以上を指定してな！",
                ephemeral=True
            )

            return

        if minutes > 10080:

            await interaction.response.send_message(
                "最大7日までにしてな！",
                ephemeral=True
            )

            return

        if len(message) > 500:

            await interaction.response.send_message(
                "文章は500文字以内にしてな！",
                ephemeral=True
            )

            return

        try:

            await self.bot.db.add_reminder(
                interaction.user.id,
                interaction.channel.id,
                message,
                minutes
            )

            await interaction.response.send_message(
                f"⏰ {minutes}分後に"
                f"「{message}」って知らせるで！",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/remind failed: {e}"
            )

            await interaction.response.send_message(
                "リマインダー登録中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Memory
    # ==========================================================================

    @app_commands.command(
        name="memory",
        description="茜が覚えている会話履歴を確認"
    )
    async def memory(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能はサーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            count = await self.bot.db.count_conversation_history(
                interaction.guild.id,
                interaction.channel.id,
                interaction.user.id
            )

            active_count = min(
                count,
                Config.MEMORY_MESSAGE_LIMIT
            )

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🧠 茜の会話メモリー",
                    description=(
                        f"保存履歴: **{count}件**\n"
                        f"参照最大: "
                        f"**{active_count}件**\n"
                        f"保存期間: "
                        f"**{Config.MEMORY_RETENTION_DAYS}日**"
                    ),
                    color=discord.Color.purple()
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/memory failed: {e}"
            )

            await interaction.response.send_message(
                "記憶情報を確認できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Forget
    # ==========================================================================

    @app_commands.command(
        name="forget",
        description="自分のAI会話履歴を削除"
    )
    async def forget(
        self,
        interaction: discord.Interaction,
        all_channels: bool = False
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能はサーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            if all_channels:

                deleted = await self.bot.db.clear_all_user_history(
                    interaction.guild.id,
                    interaction.user.id
                )

            else:

                deleted = await self.bot.db.clear_conversation_history(
                    interaction.guild.id,
                    interaction.channel.id,
                    interaction.user.id
                )

            await interaction.response.send_message(
                f"🧹 **{deleted}件** 消したで！",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/forget failed: {e}"
            )

            await interaction.response.send_message(
                "履歴削除中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Profile - V33
    # ==========================================================================

    @app_commands.command(
        name="profile",
        description="プロフィールを表示"
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        member: Optional[
            discord.Member
        ] = None
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能はサーバー内専用やで。",
                ephemeral=True
            )

            return

        target = (
            member
            or interaction.user
        )

        try:

            await self.bot.db.evaluate_progress_unlocks(
                interaction.guild.id,
                target.id
            )

            level_info = await self.bot.db.get_level_info(
                target.id
            )

            stats = await self.bot.db.get_user_stats(
                interaction.guild.id,
                target.id
            )

            achievements = await self.bot.db.get_user_achievements(
                interaction.guild.id,
                target.id
            )

            titles = await self.bot.db.get_user_titles(
                interaction.guild.id,
                target.id
            )

            equipped_key = await self.bot.db.get_equipped_title(
                interaction.guild.id,
                target.id
            )

            weekly_xp = await self.bot.db.get_user_weekly_xp(
                interaction.guild.id,
                target.id
            )

            weekly_rank = await self.bot.db.get_weekly_rank(
                interaction.guild.id,
                target.id
            )

            if (
                equipped_key
                and equipped_key
                in Config.TITLES
            ):

                equipped_title = Config.TITLES[
                    equipped_key
                ]["name"]

            else:

                equipped_title = "称号なし"

            percentage = level_info[
                "percentage"
            ]

            filled = int(
                percentage
                / 10
            )

            filled = max(
                0,
                min(
                    filled,
                    10
                )
            )

            progress_bar = (
                "🟩" * filled
                + "⬜" * (
                    10 - filled
                )
            )

            preview_lines = []

            for (
                achievement_key,
                unlocked_at
            ) in achievements[
                -Config.PROFILE_ACHIEVEMENT_PREVIEW:
            ]:

                data = Config.ACHIEVEMENTS.get(
                    achievement_key
                )

                if data:

                    preview_lines.append(
                        f"{data['emoji']} "
                        f"{data['name']}"
                    )

            embed = discord.Embed(
                title=(
                    f"🌸 "
                    f"{target.display_name}"
                    " のプロフィール"
                ),
                color=discord.Color.pink()
            )

            embed.set_thumbnail(
                url=target.display_avatar.url
            )

            embed.add_field(
                name="🎖️ 称号",
                value=f"**{equipped_title}**",
                inline=False
            )

            embed.add_field(
                name="📊 レベル",
                value=(
                    f"**Lv."
                    f"{level_info['level']}**"
                ),
                inline=True
            )

            embed.add_field(
                name="✨ XP",
                value=(
                    f"**{level_info['xp']} / "
                    f"{level_info['required_xp']}**"
                ),
                inline=True
            )

            embed.add_field(
                name="🎯 次まで",
                value=(
                    f"**"
                    f"{level_info['remaining_xp']} XP"
                    f"**"
                ),
                inline=True
            )

            embed.add_field(
                name="進行度",
                value=(
                    f"{progress_bar}\n"
                    f"{percentage:.1f}%"
                ),
                inline=False
            )

            # ==================================================================
            # V33 Weekly
            # ==================================================================

            rank_text = (
                f"#{weekly_rank}"
                if weekly_rank
                else "順位なし"
            )

            embed.add_field(
                name="🔥 今週XP",
                value=f"**{weekly_xp} XP**",
                inline=True
            )

            if Config.SHOW_WEEKLY_RANK_IN_PROFILE:

                embed.add_field(
                    name="🏆 週間順位",
                    value=f"**{rank_text}**",
                    inline=True
                )

            embed.add_field(
                name="💬 メッセージ",
                value=(
                    f"**"
                    f"{stats['message_count']}回"
                    f"**"
                ),
                inline=True
            )

            embed.add_field(
                name="🤖 AI会話",
                value=(
                    f"**"
                    f"{stats['ai_chat_count']}回"
                    f"**"
                ),
                inline=True
            )

            embed.add_field(
                name="🔮 運勢",
                value=(
                    f"**"
                    f"{stats['fortune_count']}日"
                    f"**"
                ),
                inline=True
            )

            embed.add_field(
                name="📩 Ticket",
                value=(
                    f"**"
                    f"{stats['ticket_count']}回"
                    f"**"
                ),
                inline=True
            )

            embed.add_field(
                name="🏆 実績",
                value=(
                    f"**{len(achievements)} / "
                    f"{len(Config.ACHIEVEMENTS)}**"
                ),
                inline=True
            )

            embed.add_field(
                name="🎖️ 称号",
                value=(
                    f"**{len(titles)} / "
                    f"{len(Config.TITLES)}**"
                ),
                inline=True
            )

            embed.add_field(
                name="最近の実績",
                value=(
                    "\n".join(
                        preview_lines
                    )
                    or "まだ実績なし"
                ),
                inline=False
            )

            embed.set_footer(
                text=(
                    "/weekly /rankings "
                    "でも順位を確認できるで"
                )
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/profile failed: {e}"
            )

            await interaction.response.send_message(
                "プロフィール取得中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Fortune
    # ==========================================================================

    @app_commands.command(
        name="fortune",
        description="今日の運勢を占う"
    )
    async def fortune(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能はサーバー内専用やで。",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            guild_id = interaction.guild.id
            user_id = interaction.user.id

            existing = await self.bot.db.get_today_fortune(
                guild_id,
                user_id
            )

            is_new = existing is None

            if existing:

                fortune_key = existing[0]
                score = int(
                    existing[1]
                )

            else:

                today = datetime.now(
                    JST
                ).strftime(
                    "%Y-%m-%d"
                )

                seed_text = (
                    f"{guild_id}:"
                    f"{user_id}:"
                    f"{today}:"
                    "akane-v33"
                )

                digest = hashlib.sha256(
                    seed_text.encode(
                        "utf-8"
                    )
                ).hexdigest()

                rng = random.Random(
                    int(
                        digest[:16],
                        16
                    )
                )

                score = rng.randint(
                    1,
                    100
                )

                if score >= 96:
                    fortune_key = "super_lucky"
                elif score >= 81:
                    fortune_key = "great_lucky"
                elif score >= 61:
                    fortune_key = "lucky"
                elif score >= 41:
                    fortune_key = "small_lucky"
                elif score >= 21:
                    fortune_key = "neutral"
                else:
                    fortune_key = "careful"

                await self.bot.db.save_today_fortune(
                    guild_id,
                    user_id,
                    fortune_key,
                    score
                )

                await self.bot.db.increment_fortune_count(
                    guild_id,
                    user_id
                )

            fortunes = {
                "super_lucky": (
                    "🌈 超大吉",
                    "今日はかなりええ日になりそうや！"
                ),
                "great_lucky": (
                    "✨ 大吉",
                    "ええ流れ来てるで！"
                ),
                "lucky": (
                    "🌸 吉",
                    "なかなかええ感じやな。"
                ),
                "small_lucky": (
                    "🍀 小吉",
                    "小さなラッキーがありそうや。"
                ),
                "neutral": (
                    "☕ 末吉",
                    "普段通りが一番やで。"
                ),
                "careful": (
                    "🌧️ 注意",
                    "今日は慎重めがええかもな。"
                ),
            }

            fortune_name, fortune_message = fortunes[
                fortune_key
            ]

            embed = discord.Embed(
                title="🔮 今日の運勢",
                description=(
                    f"## {fortune_name}\n\n"
                    f"{fortune_message}"
                ),
                color=discord.Color.purple()
            )

            embed.add_field(
                name="運勢スコア",
                value=f"**{score} / 100**"
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

            if is_new:

                unlocks = await self.bot.db.evaluate_progress_unlocks(
                    guild_id,
                    user_id
                )

                await self._send_unlock_notifications(
                    interaction,
                    unlocks
                )

        except Exception as e:

            logger.exception(
                f"/fortune failed: {e}"
            )

            await interaction.followup.send(
                "占い中にエラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Achievements
    # ==========================================================================

    @app_commands.command(
        name="achievements",
        description="実績一覧を表示"
    )
    async def achievements(
        self,
        interaction: discord.Interaction,
        member: Optional[
            discord.Member
        ] = None
    ):

        target = (
            member
            or interaction.user
        )

        try:

            await self.bot.db.evaluate_progress_unlocks(
                interaction.guild.id,
                target.id
            )

            rows = await self.bot.db.get_user_achievements(
                interaction.guild.id,
                target.id
            )

            unlocked = {
                row[0]
                for row in rows
            }

            lines = []

            for key, data in Config.ACHIEVEMENTS.items():

                mark = (
                    "✅"
                    if key in unlocked
                    else "🔒"
                )

                lines.append(
                    f"{mark} "
                    f"{data['emoji']} "
                    f"**{data['name']}**\n"
                    f"　{data['description']}"
                )

            await interaction.response.send_message(
                embed=discord.Embed(
                    title=(
                        f"🏆 "
                        f"{target.display_name}"
                        " の実績"
                    ),
                    description="\n\n".join(
                        lines
                    ),
                    color=discord.Color.gold()
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/achievements failed: {e}"
            )

            await interaction.response.send_message(
                "実績一覧を取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Titles
    # ==========================================================================

    @app_commands.command(
        name="titles",
        description="獲得済み称号を表示"
    )
    async def titles(
        self,
        interaction: discord.Interaction
    ):

        try:

            await self.bot.db.evaluate_progress_unlocks(
                interaction.guild.id,
                interaction.user.id
            )

            rows = await self.bot.db.get_user_titles(
                interaction.guild.id,
                interaction.user.id
            )

            if not rows:

                await interaction.response.send_message(
                    "まだ称号を持ってへんで。",
                    ephemeral=True
                )

                return

            lines = []

            for (
                title_key,
                equipped,
                unlocked_at
            ) in rows:

                data = Config.TITLES.get(
                    title_key
                )

                if not data:

                    continue

                marker = (
                    " 👈 **装備中**"
                    if equipped
                    else ""
                )

                lines.append(
                    f"`{title_key}` "
                    f"{data['name']}"
                    f"{marker}\n"
                    f"　{data['description']}"
                )

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🎖️ 獲得済み称号",
                    description="\n\n".join(
                        lines
                    ),
                    color=discord.Color.blurple()
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/titles failed: {e}"
            )

            await interaction.response.send_message(
                "称号一覧を取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Title Set
    # ==========================================================================

    @app_commands.command(
        name="title_set",
        description="プロフィールの称号を変更"
    )
    async def title_set(
        self,
        interaction: discord.Interaction,
        title_key: str
    ):

        title_key = (
            title_key
            .strip()
            .lower()
        )

        try:

            if title_key not in Config.TITLES:

                await interaction.response.send_message(
                    "その称号キーは存在せえへんで。",
                    ephemeral=True
                )

                return

            if not await self.bot.db.has_title(
                interaction.guild.id,
                interaction.user.id,
                title_key
            ):

                await interaction.response.send_message(
                    "その称号はまだ持ってへんで。",
                    ephemeral=True
                )

                return

            await self.bot.db.set_equipped_title(
                interaction.guild.id,
                interaction.user.id,
                title_key
            )

            await interaction.response.send_message(
                (
                    "🎖️ 表示称号を "
                    f"**{Config.TITLES[title_key]['name']}** "
                    "に変更したで！"
                ),
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/title_set failed: {e}"
            )

            await interaction.response.send_message(
                "称号変更中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # V33 Weekly
    # ==========================================================================

    @app_commands.command(
        name="weekly",
        description="今週のXPランキング"
    )
    async def weekly(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            rows = await self.bot.db.get_weekly_xp_leaderboard(
                interaction.guild.id,
                Config.RANKING_LIMIT
            )

            week_key = self.bot.db.current_week_key()

            lines = []

            for position, (
                user_id,
                xp
            ) in enumerate(
                rows,
                1
            ):

                name = self._member_name(
                    interaction.guild,
                    user_id
                )

                lines.append(
                    f"{self._ranking_medal(position)} "
                    f"**{name}** — "
                    f"**{xp} XP**"
                )

            user_xp = await self.bot.db.get_user_weekly_xp(
                interaction.guild.id,
                interaction.user.id
            )

            user_rank = await self.bot.db.get_weekly_rank(
                interaction.guild.id,
                interaction.user.id
            )

            embed = discord.Embed(
                title="🔥 今週のXPランキング",
                description=(
                    "\n".join(
                        lines
                    )
                    or "まだ週間XPデータがないで。"
                ),
                color=discord.Color.orange()
            )

            embed.add_field(
                name="あなた",
                value=(
                    f"XP: **{user_xp}**\n"
                    f"順位: "
                    f"**"
                    f"{('#' + str(user_rank)) if user_rank else '順位なし'}"
                    f"**"
                ),
                inline=False
            )

            embed.set_footer(
                text=(
                    f"{week_key} / "
                    "JST・月曜〜日曜"
                )
            )

            await interaction.response.send_message(
                embed=embed
            )

        except Exception as e:

            logger.exception(
                f"/weekly failed: {e}"
            )

            await interaction.response.send_message(
                "週間ランキング取得中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # V33 Rankings
    # ==========================================================================

    @app_commands.command(
        name="rankings",
        description="サーバー内ランキング"
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(
                name="🔥 週間XP",
                value="weekly"
            ),
            app_commands.Choice(
                name="💬 発言数",
                value="messages"
            ),
            app_commands.Choice(
                name="🤖 AI会話",
                value="ai"
            ),
            app_commands.Choice(
                name="🏆 実績数",
                value="achievements"
            ),
        ]
    )
    async def rankings(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str]
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            if category.value == "weekly":

                rows = await self.bot.db.get_weekly_xp_leaderboard(
                    interaction.guild.id,
                    Config.RANKING_LIMIT
                )

                title = "🔥 週間XPランキング"
                suffix = "XP"

            elif category.value == "messages":

                rows = await self.bot.db.get_message_leaderboard(
                    interaction.guild.id,
                    Config.RANKING_LIMIT
                )

                title = "💬 発言数ランキング"
                suffix = "発言"

            elif category.value == "ai":

                rows = await self.bot.db.get_ai_leaderboard(
                    interaction.guild.id,
                    Config.RANKING_LIMIT
                )

                title = "🤖 AI会話ランキング"
                suffix = "回"

            else:

                rows = await self.bot.db.get_achievement_leaderboard(
                    interaction.guild.id,
                    Config.RANKING_LIMIT
                )

                title = "🏆 実績ランキング"
                suffix = "個"

            lines = []

            for position, (
                user_id,
                value
            ) in enumerate(
                rows,
                1
            ):

                name = self._member_name(
                    interaction.guild,
                    user_id
                )

                lines.append(
                    f"{self._ranking_medal(position)} "
                    f"**{name}** — "
                    f"**{value} {suffix}**"
                )

            embed = discord.Embed(
                title=title,
                description=(
                    "\n".join(
                        lines
                    )
                    or "まだデータがないで。"
                ),
                color=discord.Color.gold()
            )

            embed.set_footer(
                text=(
                    f"TOP {Config.RANKING_LIMIT} "
                    "・このサーバー内のみ"
                )
            )

            await interaction.response.send_message(
                embed=embed
            )

        except Exception as e:

            logger.exception(
                f"/rankings failed: {e}"
            )

            await interaction.response.send_message(
                "ランキング取得中に"
                "エラーが起きたで。",
                ephemeral=True
            )


# ==============================================================================
# Cog Setup
# ==============================================================================

async def setup(
    bot
):

    await bot.add_cog(
        GeneralCog(
            bot
        )
    )
