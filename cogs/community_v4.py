from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz
from discord import app_commands

from config import JST
from cogs.general_v4 import GeneralCog as ReleaseDGeneralCog
from services.community_capabilities import (
    build_community_capability_dispatcher,
    dispatch_event_create,
    dispatch_message_search,
    dispatch_poll_create,
)
from views.event_view import EventView


logger = logging.getLogger("AkaneBot")


class GeneralCog(ReleaseDGeneralCog):
    """Release E strangler for the remaining general community commands."""

    def __init__(self, bot):
        super().__init__(bot)
        self._community_capability_dispatcher = build_community_capability_dispatcher(self)

    # CommunityCapabilityDataSource -------------------------------------------------
    async def search_messages(
        self,
        *,
        context,
        keyword: str,
        target_channel_id: int | None,
        target_user_id: int | None,
        days: int | None,
    ):
        interaction = context.interaction
        channel = interaction.channel
        if target_channel_id is not None and interaction.guild is not None:
            channel = interaction.guild.get_channel(target_channel_id) or channel

        after = (
            datetime.now(pytz.utc) - timedelta(days=days)
            if days
            else None
        )
        found = []
        async for message in channel.history(limit=1000, after=after):
            if target_user_id is not None and message.author.id != target_user_id:
                continue
            if keyword in message.content:
                found.append(message)
                if len(found) >= 100:
                    break
        return {"messages": found}

    async def create_event(self, *, context, title: str, date: str, time: str):
        interaction = context.interaction
        naive = datetime.strptime(f"{date} {time}", "%Y/%m/%d %H:%M")
        event_datetime = JST.localize(naive)
        timestamp = int(event_datetime.timestamp())

        embed = discord.Embed(
            title=f"📅 {title}",
            description=f"日時: <t:{timestamp}:F>",
            color=discord.Color.green(),
        )
        embed.add_field(name="【参加】", value="なし")
        embed.add_field(name="【不参加】", value="なし")
        await interaction.response.send_message(embed=embed, view=EventView())

        scheduled_created = False
        if interaction.guild is not None:
            try:
                await interaction.guild.create_scheduled_event(
                    name=title,
                    start_time=event_datetime,
                    end_time=event_datetime + timedelta(hours=2),
                    location="Discord",
                    entity_type=discord.EntityType.external,
                    privacy_level=discord.PrivacyLevel.guild_only,
                )
                scheduled_created = True
            except Exception as exc:
                logger.exception(f"Scheduled event failed: {exc}")

        return {"timestamp": timestamp, "scheduled_created": scheduled_created}

    async def create_poll(self, *, context, question: str, options: tuple[str, ...]):
        interaction = context.interaction
        emojis = ("1️⃣", "2️⃣", "3️⃣", "4️⃣")
        description = "\n".join(
            f"{emojis[index]} {option}" for index, option in enumerate(options)
        )
        await interaction.response.send_message(
            f"📊 **{question}** #投票",
            embed=discord.Embed(description=description, color=discord.Color.gold()),
        )
        message = await interaction.original_response()
        for index in range(len(options)):
            await message.add_reaction(emojis[index])
        return {"option_count": len(options)}

    # Slash adapters ----------------------------------------------------------------
    @app_commands.command(name="event", description="イベント作成")
    async def event(self, interaction: discord.Interaction, title: str, date: str, time: str):
        try:
            await dispatch_event_create(
                self._community_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel_id,
                title=title,
                date=date,
                time=time,
                confirmed=True,
                interaction=interaction,
            )
        except ValueError:
            await interaction.response.send_message(
                "日時は `YYYY/MM/DD HH:MM` の形式で頼むで！",
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception(f"/event failed: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "イベント作成中にエラーが起きたで。",
                    ephemeral=True,
                )

    @app_commands.command(name="poll", description="投票作成")
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
    ):
        options = tuple(option for option in (option1, option2, option3, option4) if option)
        try:
            await dispatch_poll_create(
                self._community_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel_id,
                question=question,
                options=options,
                confirmed=True,
                interaction=interaction,
            )
        except Exception as exc:
            logger.exception(f"/poll failed: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "投票作成中にエラーが起きたで。",
                    ephemeral=True,
                )

    @app_commands.command(name="search", description="メッセージ検索")
    async def search(
        self,
        interaction: discord.Interaction,
        keyword: str,
        target_channel: Optional[discord.TextChannel] = None,
        member: Optional[discord.Member] = None,
        days: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await dispatch_message_search(
                self._community_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel_id,
                keyword=keyword,
                target_channel_id=target_channel.id if target_channel else None,
                target_user_id=member.id if member else None,
                days=days,
                interaction=interaction,
            )
            found = result.value["messages"]
        except Exception as exc:
            logger.exception(f"/search failed: {exc}")
            await interaction.followup.send("検索中にエラーが起きたで。", ephemeral=True)
            return

        if not found:
            await interaction.followup.send("見つからへんかったで。", ephemeral=True)
            return

        if len(found) > 20:
            text = "\n".join(
                f"[{message.created_at}] {message.author}: {message.content}"
                for message in found
            )
            await interaction.followup.send(
                f"{len(found)}件",
                file=discord.File(io.BytesIO(text.encode("utf-8")), filename="result.txt"),
                ephemeral=True,
            )
            return

        description = "\n".join(
            f"• [{message.content[:30]}]({message.jump_url})" for message in found
        )
        await interaction.followup.send(
            embed=discord.Embed(title=f"検索: {keyword}", description=description),
            ephemeral=True,
        )
