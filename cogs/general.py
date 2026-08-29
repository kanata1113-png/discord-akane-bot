import io
import logging
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

            if not result or not result.strip():
                result = Config.ERROR_MSG

            if len(result) > 4000:

                file = discord.File(
                    io.BytesIO(
                        result.encode()
                    ),
                    filename="trans.txt"
                )

                await interaction.followup.send(
                    "長すぎるからファイルにするな！",
                    file=file
                )

            else:

                await interaction.followup.send(
                    embed=discord.Embed(
                        title=f"翻訳 ({language})",
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
        description="AI辞書 (400文字解説)"
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

            if not result or not result.strip():

                await interaction.followup.send(
                    Config.ERROR_MSG,
                    ephemeral=True
                )

                return

            if len(result) > 4000:

                file = discord.File(
                    io.BytesIO(
                        result.encode()
                    ),
                    filename="define.txt"
                )

                await interaction.followup.send(
                    "長すぎるからファイルにするな！",
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
                "辞書処理中にエラーが起きたで。",
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
            min(back, 20)
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
                if message.author == interaction.user
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

            if not result or not result.strip():
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
        description="イベント(スケジュール)作成"
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
                "日時は `YYYY/MM/DD HH:MM` "
                "の形式で頼むで！",
                ephemeral=True
            )

            return

        timestamp = int(
            event_datetime.timestamp()
        )

        embed = discord.Embed(
            title=f"📅 {title}",
            description=f"日時: <t:{timestamp}:F>",
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
                    + timedelta(hours=2)
                ),
                location="Discord",
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only
            )

        except discord.Forbidden:

            logger.warning(
                "Scheduled event permission denied."
            )

        except Exception as e:

            logger.exception(
                f"Scheduled event creation failed: {e}"
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
            for option in [
                option1,
                option2,
                option3,
                option4
            ]
            if option
        ]

        emojis = [
            "1️⃣",
            "2️⃣",
            "3️⃣",
            "4️⃣"
        ]

        description = "\n".join(
            f"{emojis[index]} {option}"
            for index, option
            in enumerate(options)
        )

        await interaction.response.send_message(
            f"📊 **{question}** #投票",
            embed=discord.Embed(
                description=description,
                color=discord.Color.gold()
            )
        )

        message = await interaction.original_response()

        for index in range(len(options)):

            await message.add_reaction(
                emojis[index]
            )

    # ==========================================================================
    # Search
    # ==========================================================================

    @app_commands.command(
        name="search",
        description="検索"
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
            datetime.now(pytz.utc)
            - timedelta(days=days)
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

                    found.append(message)

                    if len(found) >= 100:
                        break

        except discord.Forbidden:

            await interaction.followup.send(
                "そのチャンネルの履歴を見る"
                "権限がないみたいや。",
                ephemeral=True
            )

            return

        if not found:

            await interaction.followup.send(
                "なし",
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
                    text.encode()
                ),
                filename="result.txt"
            )

            await interaction.followup.send(
                f"{len(found)}件 (ファイル)",
                file=file,
                ephemeral=True
            )

        else:

            description = "\n".join(
                (
                    f"• [{message.content[:30]}]"
                    f"({message.jump_url})"
                )
                for message in found
            )

            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"検索: {keyword}",
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

        level_value, xp = (
            await self.bot.db.get_user_data(
                interaction.user.id
            )
        )

        await interaction.response.send_message(
            f"📊 Lv.{level_value} (XP: {xp})",
            ephemeral=True
        )

    # ==========================================================================
    # Leaderboard
    # ==========================================================================

    @app_commands.command(
        name="leaderboard",
        description="ランキング(TOP30)"
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        rows = await self.bot.db.get_leaderboard(
            30
        )

        lines = []

        for index, (
            user_id,
            level_value,
            xp
        ) in enumerate(rows, 1):

            member = interaction.guild.get_member(
                int(user_id)
            )

            name = (
                member.display_name
                if member
                else "Unknown"
            )

            lines.append(
                f"{index}. {name} "
                f"(Lv.{level_value})"
            )

        await interaction.followup.send(
            embed=discord.Embed(
                title="🏆 ランキング",
                description=(
                    "\n".join(lines)
                    or "データなし"
                ),
                color=discord.Color.gold()
            ),
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
                "最大7日（10080分）までにしてな！",
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
                f"Reminder registration failed: {e}"
            )

            await interaction.response.send_message(
                "リマインダー登録中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # v29 Memory Status
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

            count = (
                await self.bot.db
                .count_conversation_history(
                    guild_id=interaction.guild.id,
                    channel_id=interaction.channel.id,
                    user_id=interaction.user.id
                )
            )

            active_count = min(
                count,
                Config.MEMORY_MESSAGE_LIMIT
            )

            embed = discord.Embed(
                title="🧠 茜の会話メモリー",
                description=(
                    f"このチャンネルで保存されてる履歴: "
                    f"**{count}件**\n"
                    f"次の会話で参照する最大履歴: "
                    f"**{active_count}件**\n"
                    f"保存期間: "
                    f"**{Config.MEMORY_RETENTION_DAYS}日**"
                ),
                color=discord.Color.purple()
            )

            embed.set_footer(
                text=(
                    "/forget で自分の履歴を消せるで"
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
                "記憶情報を確認できへんかったわ。",
                ephemeral=True
            )

    # ==========================================================================
    # v29 Forget
    # ==========================================================================

    @app_commands.command(
        name="forget",
        description="茜が覚えている自分の会話履歴を削除"
    )
    @app_commands.describe(
        all_channels=(
            "このサーバー内の全チャンネルの"
            "履歴を消すか"
        )
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

                deleted = (
                    await self.bot.db
                    .clear_all_user_history(
                        guild_id=interaction.guild.id,
                        user_id=interaction.user.id
                    )
                )

                await interaction.response.send_message(
                    f"🧹 このサーバーで覚えてた"
                    f"会話履歴を **{deleted}件** 消したで！",
                    ephemeral=True
                )

            else:

                deleted = (
                    await self.bot.db
                    .clear_conversation_history(
                        guild_id=interaction.guild.id,
                        channel_id=interaction.channel.id,
                        user_id=interaction.user.id
                    )
                )

                await interaction.response.send_message(
                    f"🧹 このチャンネルで覚えてた"
                    f"会話履歴を **{deleted}件** 消したで！",
                    ephemeral=True
                )

        except Exception as e:

            logger.exception(
                f"/forget failed: {e}"
            )

            await interaction.response.send_message(
                "履歴削除中にエラーが起きたで。",
                ephemeral=True
            )

async def setup(bot):

    await bot.add_cog(
        GeneralCog(bot)
    )
