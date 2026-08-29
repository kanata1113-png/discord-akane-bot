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


logger = logging.getLogger("AkaneBot")


class GeneralCog(commands.Cog):

    def __init__(self, bot):

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

            if not data:
                continue

            lines.append(
                f"🏆 実績解除: "
                f"**{data['emoji']} "
                f"{data['name']}**"
            )

        for key in title_keys:

            data = Config.TITLES.get(
                key
            )

            if not data:
                continue

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

            result = (
                await self.bot.ai.translate(
                    text,
                    language
                )
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

            result = (
                await self.bot.ai.define_word(
                    word,
                    wiki_mode
                )
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

            embed = discord.Embed(
                title=title,
                description=result,
                color=discord.Color.green()
            )

            embed.set_footer(
                text="Powered by AI Dictionary"
            )

            await interaction.followup.send(
                embed=embed
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
                if (
                    message.author
                    == interaction.user
                )
            ][:back]

            if not messages:

                await interaction.followup.send(
                    "発言が見つからんかったわ。",
                    ephemeral=True
                )

                return

            messages.reverse()

            result = (
                await self.bot.ai.summarize(
                    messages
                )
            )

            if (
                not result
                or not result.strip()
            ):

                result = Config.ERROR_MSG

            await interaction.followup.send(
                embed=discord.Embed(
                    title="📝 発言要約",
                    description=result,
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
                f"日時: "
                f"<t:{timestamp}:F>"
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
                entity_type=(
                    discord.EntityType.external
                ),
                privacy_level=(
                    discord.PrivacyLevel.guild_only
                )
            )

        except discord.Forbidden:

            logger.warning(
                "Scheduled event "
                "permission denied."
            )

        except Exception as e:

            logger.exception(
                "Scheduled event "
                f"creation failed: {e}"
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

        message = (
            await interaction
            .original_response()
        )

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

        except discord.Forbidden:

            await interaction.followup.send(
                "そのチャンネルの履歴を見る"
                "権限がないみたいや。",
                ephemeral=True
            )

            return

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
                f"{len(found)}件 "
                "(ファイル)",
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
                        f"検索: "
                        f"{keyword}"
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

            info = (
                await self.bot.db
                .get_level_info(
                    interaction.user.id
                )
            )

            await interaction.response.send_message(
                (
                    f"📊 "
                    f"**Lv.{info['level']}**\n"
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
                "レベル情報を"
                "取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Leaderboard
    # ==========================================================================

    @app_commands.command(
        name="leaderboard",
        description="ランキング TOP30"
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            rows = (
                await self.bot.db
                .get_leaderboard(
                    30
                )
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

                member = (
                    interaction.guild
                    .get_member(
                        int(
                            user_id
                        )
                    )
                )

                name = (
                    member.display_name
                    if member
                    else "Unknown"
                )

                lines.append(
                    f"{index}. "
                    f"{name} "
                    f"(Lv.{level_value} / "
                    f"XP {xp})"
                )

            await interaction.followup.send(
                embed=discord.Embed(
                    title="🏆 ランキング",
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
                "最大7日"
                "（10080分）までにしてな！",
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
                "Reminder registration "
                f"failed: {e}"
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
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            count = (
                await self.bot.db
                .count_conversation_history(
                    guild_id=(
                        interaction.guild.id
                    ),
                    channel_id=(
                        interaction.channel.id
                    ),
                    user_id=(
                        interaction.user.id
                    )
                )
            )

            active_count = min(
                count,
                Config.MEMORY_MESSAGE_LIMIT
            )

            embed = discord.Embed(
                title="🧠 茜の会話メモリー",
                description=(
                    "このチャンネルで"
                    "保存されてる履歴: "
                    f"**{count}件**\n"
                    "次の会話で参照する"
                    "最大履歴: "
                    f"**{active_count}件**\n"
                    "保存期間: "
                    f"**{Config.MEMORY_RETENTION_DAYS}日**"
                ),
                color=discord.Color.purple()
            )

            embed.set_footer(
                text=(
                    "/forget で"
                    "自分の履歴を消せるで"
                )
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/memory failed: {e}"
            )

            await interaction.response.send_message(
                "記憶情報を"
                "確認できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # Forget
    # ==========================================================================

    @app_commands.command(
        name="forget",
        description="茜が覚えている自分の会話履歴を削除"
    )
    @app_commands.describe(
        all_channels=(
            "このサーバー内の"
            "全チャンネル履歴を消すか"
        )
    )
    async def forget(
        self,
        interaction: discord.Interaction,
        all_channels: bool = False
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            if all_channels:

                deleted = (
                    await self.bot.db
                    .clear_all_user_history(
                        guild_id=(
                            interaction.guild.id
                        ),
                        user_id=(
                            interaction.user.id
                        )
                    )
                )

                await interaction.response.send_message(
                    "🧹 このサーバーで覚えてた"
                    f"会話履歴を **{deleted}件** "
                    "消したで！",
                    ephemeral=True
                )

            else:

                deleted = (
                    await self.bot.db
                    .clear_conversation_history(
                        guild_id=(
                            interaction.guild.id
                        ),
                        channel_id=(
                            interaction.channel.id
                        ),
                        user_id=(
                            interaction.user.id
                        )
                    )
                )

                await interaction.response.send_message(
                    "🧹 このチャンネルで覚えてた"
                    f"会話履歴を **{deleted}件** "
                    "消したで！",
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
    # V32 Profile
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
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        target = (
            member
            or interaction.user
        )

        try:

            level_info = (
                await self.bot.db
                .get_level_info(
                    target.id
                )
            )

            stats = (
                await self.bot.db
                .get_user_stats(
                    interaction.guild.id,
                    target.id
                )
            )

            achievements = (
                await self.bot.db
                .get_user_achievements(
                    interaction.guild.id,
                    target.id
                )
            )

            titles = (
                await self.bot.db
                .get_user_titles(
                    interaction.guild.id,
                    target.id
                )
            )

            equipped_key = (
                await self.bot.db
                .get_equipped_title(
                    interaction.guild.id,
                    target.id
                )
            )

            # ==================================================================
            # Title
            # ==================================================================

            if (
                equipped_key
                and equipped_key
                in Config.TITLES
            ):

                equipped_title = (
                    Config.TITLES[
                        equipped_key
                    ]["name"]
                )

            else:

                equipped_title = (
                    "称号なし"
                )

            # ==================================================================
            # XP Bar
            # ==================================================================

            percentage = (
                level_info[
                    "percentage"
                ]
            )

            bar_length = 10

            filled = int(
                percentage
                / 100
                * bar_length
            )

            filled = max(
                0,
                min(
                    filled,
                    bar_length
                )
            )

            progress_bar = (
                "🟩" * filled
                + "⬜" * (
                    bar_length
                    - filled
                )
            )

            # ==================================================================
            # Achievement Preview
            # ==================================================================

            preview_lines = []

            for (
                achievement_key,
                unlocked_at
            ) in achievements[
                -Config.PROFILE_ACHIEVEMENT_PREVIEW:
            ]:

                data = (
                    Config.ACHIEVEMENTS.get(
                        achievement_key
                    )
                )

                if not data:
                    continue

                preview_lines.append(
                    f"{data['emoji']} "
                    f"{data['name']}"
                )

            achievement_preview = (
                "\n".join(
                    preview_lines
                )
                if preview_lines
                else "まだ実績なし"
            )

            # ==================================================================
            # Embed
            # ==================================================================

            embed = discord.Embed(
                title=(
                    f"🌸 "
                    f"{target.display_name}"
                    f" のプロフィール"
                ),
                color=discord.Color.pink()
            )

            embed.set_thumbnail(
                url=(
                    target
                    .display_avatar
                    .url
                )
            )

            embed.add_field(
                name="🎖️ 称号",
                value=(
                    f"**{equipped_title}**"
                ),
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
                    f"**"
                    f"{level_info['xp']} "
                    f"/ "
                    f"{level_info['required_xp']}"
                    f"**"
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
                name="🎖️ 称号数",
                value=(
                    f"**{len(titles)} / "
                    f"{len(Config.TITLES)}**"
                ),
                inline=True
            )

            embed.add_field(
                name="最近の実績",
                value=achievement_preview,
                inline=False
            )

            embed.set_footer(
                text=(
                    "/achievements /titles "
                    "でも確認できるで"
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
    # V32 Fortune
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
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            guild_id = (
                interaction.guild.id
            )

            user_id = (
                interaction.user.id
            )

            existing = (
                await self.bot.db
                .get_today_fortune(
                    guild_id,
                    user_id
                )
            )

            is_new = (
                existing is None
            )

            # ==================================================================
            # その日の結果を固定
            # ==================================================================

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
                    "akane-v32"
                )

                digest = hashlib.sha256(
                    seed_text.encode(
                        "utf-8"
                    )
                ).hexdigest()

                seed = int(
                    digest[:16],
                    16
                )

                rng = random.Random(
                    seed
                )

                score = rng.randint(
                    1,
                    100
                )

                if score >= 96:

                    fortune_key = (
                        "super_lucky"
                    )

                elif score >= 81:

                    fortune_key = (
                        "great_lucky"
                    )

                elif score >= 61:

                    fortune_key = (
                        "lucky"
                    )

                elif score >= 41:

                    fortune_key = (
                        "small_lucky"
                    )

                elif score >= 21:

                    fortune_key = (
                        "neutral"
                    )

                else:

                    fortune_key = (
                        "careful"
                    )

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

            # ==================================================================
            # Result
            # ==================================================================

            fortunes = {
                "super_lucky": {
                    "name": "🌈 超大吉",
                    "message": (
                        "今日はかなりええ日になりそうや！"
                        "思い切って動くんもアリやで。"
                    ),
                },

                "great_lucky": {
                    "name": "✨ 大吉",
                    "message": (
                        "ええ流れ来てるで！"
                        "やりたかったことを"
                        "進めるのに向いてそうや。"
                    ),
                },

                "lucky": {
                    "name": "🌸 吉",
                    "message": (
                        "なかなかええ感じやな。"
                        "焦らず動けば"
                        "良い結果につながりそうやで。"
                    ),
                },

                "small_lucky": {
                    "name": "🍀 小吉",
                    "message": (
                        "小さなラッキーが"
                        "ありそうな日や。"
                        "身近なことを大事にな。"
                    ),
                },

                "neutral": {
                    "name": "☕ 末吉",
                    "message": (
                        "今日は無理に勝負せんでもええ日や。"
                        "普段通りが一番やで。"
                    ),
                },

                "careful": {
                    "name": "🌧️ 注意",
                    "message": (
                        "今日はちょっと慎重めがええかもな。"
                        "忘れ物と勢い任せには注意やで。"
                    ),
                },
            }

            fortune_data = (
                fortunes[
                    fortune_key
                ]
            )

            lucky_items = [
                "コーヒー",
                "チョコ",
                "イヤホン",
                "本",
                "赤いもの",
                "青いもの",
                "温かい飲み物",
                "お気に入りの曲",
                "甘いもの",
                "メモ帳",
            ]

            item_seed = (
                score
                + user_id
                + interaction.guild.id
            )

            lucky_item = lucky_items[
                item_seed
                % len(
                    lucky_items
                )
            ]

            embed = discord.Embed(
                title=(
                    "🔮 今日の運勢"
                ),
                description=(
                    f"## "
                    f"{fortune_data['name']}\n\n"
                    f"{fortune_data['message']}"
                ),
                color=discord.Color.purple()
            )

            embed.add_field(
                name="運勢スコア",
                value=f"**{score} / 100**",
                inline=True
            )

            embed.add_field(
                name="ラッキーアイテム",
                value=f"**{lucky_item}**",
                inline=True
            )

            embed.set_footer(
                text=(
                    "今日中は何回見ても"
                    "同じ結果やで"
                )
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

            # ==================================================================
            # Unlock
            # ==================================================================

            if is_new:

                unlocks = (
                    await self.bot.db
                    .evaluate_progress_unlocks(
                        guild_id,
                        user_id
                    )
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
                "占い中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # V32 Achievements
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

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        target = (
            member
            or interaction.user
        )

        try:

            # 既存レベルなどもここで再評価
            await self.bot.db.evaluate_progress_unlocks(
                interaction.guild.id,
                target.id
            )

            unlocked_rows = (
                await self.bot.db
                .get_user_achievements(
                    interaction.guild.id,
                    target.id
                )
            )

            unlocked_keys = {
                row[0]
                for row in unlocked_rows
            }

            lines = []

            for key, data in (
                Config.ACHIEVEMENTS.items()
            ):

                if key in unlocked_keys:

                    mark = "✅"

                else:

                    mark = "🔒"

                lines.append(
                    f"{mark} "
                    f"{data['emoji']} "
                    f"**{data['name']}**\n"
                    f"　{data['description']}"
                )

            embed = discord.Embed(
                title=(
                    f"🏆 "
                    f"{target.display_name}"
                    " の実績"
                ),
                description="\n\n".join(
                    lines
                ),
                color=discord.Color.gold()
            )

            embed.set_footer(
                text=(
                    f"{len(unlocked_keys)} / "
                    f"{len(Config.ACHIEVEMENTS)} "
                    "解除"
                )
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/achievements failed: {e}"
            )

            await interaction.response.send_message(
                "実績一覧を"
                "取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # V32 Titles
    # ==========================================================================

    @app_commands.command(
        name="titles",
        description="獲得済み称号を表示"
    )
    async def titles(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            guild_id = (
                interaction.guild.id
            )

            user_id = (
                interaction.user.id
            )

            await self.bot.db.evaluate_progress_unlocks(
                guild_id,
                user_id
            )

            rows = (
                await self.bot.db
                .get_user_titles(
                    guild_id,
                    user_id
                )
            )

            if not rows:

                await interaction.response.send_message(
                    "まだ称号を"
                    "持ってへんみたいや。",
                    ephemeral=True
                )

                return

            lines = []

            for (
                title_key,
                equipped,
                unlocked_at
            ) in rows:

                data = (
                    Config.TITLES.get(
                        title_key
                    )
                )

                if not data:
                    continue

                equipped_text = (
                    " 👈 **装備中**"
                    if equipped
                    else ""
                )

                lines.append(
                    f"`{title_key}` "
                    f"{data['name']}"
                    f"{equipped_text}\n"
                    f"　{data['description']}"
                )

            embed = discord.Embed(
                title="🎖️ 獲得済み称号",
                description="\n\n".join(
                    lines
                ),
                color=discord.Color.blurple()
            )

            embed.set_footer(
                text=(
                    "/title_set で"
                    "プロフィール表示称号を変更"
                )
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/titles failed: {e}"
            )

            await interaction.response.send_message(
                "称号一覧を"
                "取得できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # V32 Title Set
    # ==========================================================================

    @app_commands.command(
        name="title_set",
        description="プロフィールに表示する称号を変更"
    )
    @app_commands.describe(
        title_key=(
            "/titles に表示される"
            "英数字のキー"
        )
    )
    async def title_set(
        self,
        interaction: discord.Interaction,
        title_key: str
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        title_key = (
            title_key
            .strip()
            .lower()
        )

        try:

            if (
                title_key
                not in Config.TITLES
            ):

                await interaction.response.send_message(
                    "その称号キーは"
                    "存在せえへんで。\n"
                    "`/titles` で確認してな。",
                    ephemeral=True
                )

                return

            has_title = (
                await self.bot.db
                .has_title(
                    interaction.guild.id,
                    interaction.user.id,
                    title_key
                )
            )

            if not has_title:

                await interaction.response.send_message(
                    "その称号は"
                    "まだ獲得してへんで。",
                    ephemeral=True
                )

                return

            await self.bot.db.set_equipped_title(
                interaction.guild.id,
                interaction.user.id,
                title_key
            )

            data = (
                Config.TITLES[
                    title_key
                ]
            )

            await interaction.response.send_message(
                f"🎖️ 表示称号を "
                f"**{data['name']}** "
                "に変更したで！",
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


# ==============================================================================
# Cog Setup
# ==============================================================================

async def setup(bot):

    await bot.add_cog(
        GeneralCog(bot)
    )
