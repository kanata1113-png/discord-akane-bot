from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timedelta
from typing import Literal, Optional, Union

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

logger = logging.getLogger("AkaneBot")
EventChannel = Union[discord.VoiceChannel, discord.StageChannel]


class GeneralCog(ReleaseDGeneralCog):
    def __init__(self, bot):
        super().__init__(bot)
        self._community_capability_dispatcher = build_community_capability_dispatcher(self)

    async def search_messages(self, *, context, keyword: str, target_channel_id: int | None, target_user_id: int | None, days: int | None):
        interaction = context.interaction
        channel = interaction.channel
        if target_channel_id is not None and interaction.guild is not None:
            channel = interaction.guild.get_channel(target_channel_id) or channel
        after = datetime.now(pytz.utc) - timedelta(days=days) if days else None
        found = []
        async for message in channel.history(limit=1000, after=after):
            if target_user_id is not None and message.author.id != target_user_id:
                continue
            if keyword in message.content:
                found.append(message)
                if len(found) >= 100:
                    break
        return {"messages": found}

    @staticmethod
    def _parse_event_datetime(value: str) -> datetime:
        naive = datetime.strptime(value.strip(), "%Y/%m/%d %H:%M")
        return JST.localize(naive)

    async def create_event(self, *, context, name: str, start: str, end: str | None, event_type: str, location: str | None, event_channel_id: int | None, description: str | None):
        interaction = context.interaction
        guild = interaction.guild
        if guild is None:
            raise ValueError("guild_required")
        start_time = self._parse_event_datetime(start)
        end_time = self._parse_event_datetime(end) if end else None
        if start_time <= datetime.now(JST):
            raise ValueError("start_must_be_future")
        if end_time is not None and end_time <= start_time:
            raise ValueError("end_must_be_after_start")

        event_type = event_type.strip().lower()
        kwargs = {
            "name": name.strip(),
            "start_time": start_time,
            "privacy_level": discord.PrivacyLevel.guild_only,
            "description": description.strip() if description else None,
            "reason": f"Akane event_create requested by {interaction.user} ({interaction.user.id})",
        }
        if event_type == "external":
            if not location or not location.strip():
                raise ValueError("external_location_required")
            if end_time is None:
                raise ValueError("external_end_required")
            kwargs.update(entity_type=discord.EntityType.external, location=location.strip(), end_time=end_time)
        elif event_type in {"voice", "stage"}:
            if event_channel_id is None:
                raise ValueError("event_channel_required")
            channel = guild.get_channel(int(event_channel_id))
            expected = discord.VoiceChannel if event_type == "voice" else discord.StageChannel
            if not isinstance(channel, expected):
                raise ValueError("event_channel_type_mismatch")
            kwargs["channel"] = channel
            if end_time is not None:
                kwargs["end_time"] = end_time
        else:
            raise ValueError("invalid_event_type")

        scheduled = await guild.create_scheduled_event(**kwargs)
        event_url = getattr(scheduled, "url", None)
        event_id = int(scheduled.id)
        timestamp = int(start_time.timestamp())
        type_label = {"external": "その他/外部", "voice": "ボイスチャンネル", "stage": "ステージチャンネル"}[event_type]
        lines = ["✅ Discord公式のスケジュールイベントを作成したで。", f"**{scheduled.name}**", f"開始: <t:{timestamp}:F>", f"形式: {type_label}"]
        lines.append(f"[イベントを開く]({event_url})" if event_url else f"イベントID: `{event_id}`")
        if interaction.response.is_done():
            await interaction.followup.send("\n".join(lines), ephemeral=True)
        else:
            await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return {"scheduled_event_id": event_id, "scheduled_event_url": event_url, "event_type": event_type, "timestamp": timestamp}

    async def create_poll(self, *, context, question: str, options: tuple[str, ...]):
        interaction = context.interaction
        emojis = ("1️⃣", "2️⃣", "3️⃣", "4️⃣")
        description = "\n".join(f"{emojis[index]} {option}" for index, option in enumerate(options))
        await interaction.response.send_message(f"📊 **{question}** #投票", embed=discord.Embed(description=description, color=discord.Color.gold()))
        message = await interaction.original_response()
        for index in range(len(options)):
            await message.add_reaction(emojis[index])
        return {"option_count": len(options)}

    @app_commands.command(name="event_create", description="Discord公式スケジュールイベントを作成")
    @app_commands.describe(name="イベント名", start="開始日時（YYYY/MM/DD HH:MM、日本時間）", end="終了日時（YYYY/MM/DD HH:MM、日本時間。外部イベントは必須）", event_type="開催形式", location="外部/その他の開催場所・URL", event_channel="ボイス/ステージの開催チャンネル", description="イベント説明")
    async def event(
        self,
        interaction: discord.Interaction,
        name: str,
        start: str,
        event_type: Literal["external", "voice", "stage"] = "external",
        end: Optional[str] = None,
        location: Optional[str] = None,
        event_channel: Optional[EventChannel] = None,
        description: Optional[str] = None,
    ):
        try:
            await dispatch_event_create(
                self._community_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel_id,
                name=name,
                start=start,
                end=end,
                event_type=event_type,
                location=location,
                event_channel_id=event_channel.id if event_channel else None,
                description=description,
                confirmed=True,
                interaction=interaction,
            )
        except ValueError as exc:
            reason = str(exc)
            messages = {
                "guild_required": "サーバー内で使ってな。",
                "start_must_be_future": "開始日時は未来の日時にしてな。",
                "end_must_be_after_start": "終了日時は開始日時より後にしてな。",
                "external_location_required": "external形式では開催場所かURLを入れてな。",
                "external_end_required": "external形式では終了日時が必要やで。",
                "event_channel_required": "voice/stage形式では開催チャンネルを選んでな。",
                "event_channel_type_mismatch": "開催形式とチャンネルの種類が合ってへんで。",
                "invalid_event_type": "開催形式が不正やで。",
            }
            message = messages.get(reason, "日時は `YYYY/MM/DD HH:MM` 形式で入力してな。")
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.Forbidden:
            message = "イベントを作成する権限が足りへんで。茜ちゃんのロールに「イベントを管理」を許可してな。"
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as exc:
            logger.exception(f"/event_create failed: {exc}")
            if interaction.response.is_done():
                await interaction.followup.send("イベント作成中にエラーが起きたで。", ephemeral=True)
            else:
                await interaction.response.send_message("イベント作成中にエラーが起きたで。", ephemeral=True)

    @app_commands.command(name="poll", description="投票作成")
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: Optional[str] = None, option4: Optional[str] = None):
        options = tuple(option for option in (option1, option2, option3, option4) if option)
        try:
            await dispatch_poll_create(self._community_capability_dispatcher, user_id=interaction.user.id, guild_id=interaction.guild.id if interaction.guild else None, channel_id=interaction.channel_id, question=question, options=options, confirmed=True, interaction=interaction)
        except Exception as exc:
            logger.exception(f"/poll failed: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message("投票作成中にエラーが起きたで。", ephemeral=True)

    @app_commands.command(name="search", description="メッセージ検索")
    async def search(self, interaction: discord.Interaction, keyword: str, target_channel: Optional[discord.TextChannel] = None, member: Optional[discord.Member] = None, days: Optional[int] = None):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await dispatch_message_search(self._community_capability_dispatcher, user_id=interaction.user.id, guild_id=interaction.guild.id if interaction.guild else None, channel_id=interaction.channel_id, keyword=keyword, target_channel_id=target_channel.id if target_channel else None, target_user_id=member.id if member else None, days=days, interaction=interaction)
            found = result.value["messages"]
        except Exception as exc:
            logger.exception(f"/search failed: {exc}")
            await interaction.followup.send("検索中にエラーが起きたで。", ephemeral=True)
            return
        if not found:
            await interaction.followup.send("見つからへんかったで。", ephemeral=True)
            return
        def search_snippet(content: str, query: str, limit: int = 48) -> str:
            clean = re.sub(r"[*_~`>#|]+", " ", content or "")
            clean = re.sub(r"\\s+", " ", clean).strip()
            if not clean:
                return "（本文なし）"
            pos = clean.casefold().find(query.casefold())
            if pos < 0:
                pos = 0
            start = max(0, pos - 12)
            snippet = clean[start:start + limit].strip()
            if start > 0:
                snippet = "…" + snippet
            if start + limit < len(clean):
                snippet += "…"
            return snippet

        visible = found[:10]
        blocks = []
        for message in visible:
            created = message.created_at.astimezone(JST).strftime("%m/%d %H:%M")
            author = getattr(message.author, "display_name", str(message.author))
            snippet = search_snippet(message.content, keyword)
            blocks.append(
                f"👤 **{author}**\n"
                f"📝 [{snippet}]({message.jump_url})\n"
                f"🕐 {created}"
            )
        description = "\n\n".join(blocks)
        footer = f"{len(found)}件中 {len(visible)}件を表示" if len(found) > len(visible) else f"{len(found)}件"
        embed = discord.Embed(
            title=f"🔎 「{keyword}」の検索結果",
            description=description,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed, ephemeral=True)
