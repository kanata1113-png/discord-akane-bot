from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz
from discord import app_commands

from cogs.admin_commands import AdminCommands as LegacyAdminCommands
from services.moderation_capabilities import (
    build_moderation_capability_dispatcher,
    dispatch_ban,
    dispatch_kick,
    dispatch_purge,
)
from views.admin_confirm_view import AdminConfirmView


logger = logging.getLogger("AkaneBot")


class AdminCommands(LegacyAdminCommands):
    """Stable admin runtime with fail-closed moderation confirmation."""

    def __init__(self, bot):
        super().__init__(bot)
        self._moderation_dispatcher = build_moderation_capability_dispatcher(self)

    @staticmethod
    async def _require_admin(interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        if interaction.guild is None or permissions is None or not permissions.administrator:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⛔ この操作は管理者専用やで！",
                    ephemeral=True,
                )
            return False
        return True

    async def kick_member(self, *, context, target_user_id: int):
        interaction = context.interaction
        guild = interaction.guild
        member = guild.get_member(target_user_id) if guild else None
        if member is None:
            raise ValueError("target_member_missing")
        await member.kick(reason=f"Executed by {interaction.user} via Akane Bot")
        logger.info(
            "Moderation capability executed | action=kick | guild=%s | target=%s | admin=%s",
            guild.id,
            target_user_id,
            interaction.user.id,
        )
        return {"target_user_id": target_user_id, "target_display": str(member)}

    async def ban_member(self, *, context, target_user_id: int):
        interaction = context.interaction
        guild = interaction.guild
        member = guild.get_member(target_user_id) if guild else None
        if member is None:
            raise ValueError("target_member_missing")
        await member.ban(reason=f"Executed by {interaction.user} via Akane Bot")
        logger.info(
            "Moderation capability executed | action=ban | guild=%s | target=%s | admin=%s",
            guild.id,
            target_user_id,
            interaction.user.id,
        )
        return {"target_user_id": target_user_id, "target_display": str(member)}

    async def purge_messages(
        self,
        *,
        context,
        amount: int,
        target_user_id: int | None,
        hours: int | None,
    ):
        interaction = context.interaction
        cutoff = datetime.now(pytz.utc) - timedelta(hours=hours) if hours else None

        def check(message):
            if target_user_id is not None and message.author.id != target_user_id:
                return False
            if cutoff and message.created_at < cutoff:
                return False
            return True

        deleted = await interaction.channel.purge(limit=amount, check=check)
        logger.info(
            "Moderation capability executed | action=purge | guild=%s | channel=%s | count=%s | admin=%s",
            interaction.guild.id,
            interaction.channel.id,
            len(deleted),
            interaction.user.id,
        )
        return {"deleted": len(deleted)}

    @app_commands.command(name="kick", description="メンバーをKick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        if not await self._require_admin(interaction):
            return
        if member.id == interaction.user.id:
            await interaction.response.send_message("自分自身をKickするんはやめとき！", ephemeral=True)
            return
        if self.bot.user and member.id == self.bot.user.id:
            await interaction.response.send_message("茜自身はKickできへんで！", ephemeral=True)
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            try:
                result = await dispatch_kick(
                    self._moderation_dispatcher,
                    user_id=confirm_interaction.user.id,
                    guild_id=confirm_interaction.guild.id,
                    channel_id=confirm_interaction.channel_id,
                    target_user_id=member.id,
                    confirmed=True,
                    interaction=confirm_interaction,
                )
                await confirm_interaction.response.edit_message(
                    content=f"✅ **{result.value['target_display']}** をKickしたで。",
                    view=None,
                )
            except discord.Forbidden:
                await confirm_interaction.response.send_message(
                    "そのメンバーをKickする権限が茜にないみたいや。",
                    ephemeral=True,
                )
            except Exception as exc:
                logger.exception("Kick capability failed: %s", exc)
                if not confirm_interaction.response.is_done():
                    await confirm_interaction.response.send_message("Kick処理中にエラーが起きたで。", ephemeral=True)

        await interaction.response.send_message(
            f"⚠️ **{member}** をKickする？\n確定するまで実行せえへんで。",
            view=AdminConfirmView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label="Kickを確定",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="ban", description="メンバーをBan")
    async def ban(self, interaction: discord.Interaction, member: discord.Member):
        if not await self._require_admin(interaction):
            return
        if member.id == interaction.user.id:
            await interaction.response.send_message("自分自身をBanするんはやめとき！", ephemeral=True)
            return
        if self.bot.user and member.id == self.bot.user.id:
            await interaction.response.send_message("茜自身はBanできへんで！", ephemeral=True)
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            try:
                result = await dispatch_ban(
                    self._moderation_dispatcher,
                    user_id=confirm_interaction.user.id,
                    guild_id=confirm_interaction.guild.id,
                    channel_id=confirm_interaction.channel_id,
                    target_user_id=member.id,
                    confirmed=True,
                    interaction=confirm_interaction,
                )
                await confirm_interaction.response.edit_message(
                    content=f"✅ **{result.value['target_display']}** をBanしたで。",
                    view=None,
                )
            except discord.Forbidden:
                await confirm_interaction.response.send_message(
                    "そのメンバーをBanする権限が茜にないみたいや。",
                    ephemeral=True,
                )
            except Exception as exc:
                logger.exception("Ban capability failed: %s", exc)
                if not confirm_interaction.response.is_done():
                    await confirm_interaction.response.send_message("Ban処理中にエラーが起きたで。", ephemeral=True)

        await interaction.response.send_message(
            f"⚠️ **{member}** をBanする？\n確定するまで実行せえへんで。",
            view=AdminConfirmView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label="Banを確定",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="purge", description="メッセージ削除")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: Optional[discord.Member] = None,
        hours: Optional[int] = None,
    ):
        if not await self._require_admin(interaction):
            return
        if amount < 1:
            await interaction.response.send_message("削除数は1以上にしてな。", ephemeral=True)
            return
        amount = min(amount, 300)
        if hours is not None and hours < 1:
            await interaction.response.send_message("時間指定は1時間以上にしてな。", ephemeral=True)
            return

        target_text = f" / 対象: {user}" if user else ""
        hours_text = f" / 過去{hours}時間" if hours else ""

        async def execute(confirm_interaction: discord.Interaction) -> None:
            try:
                await confirm_interaction.response.defer(ephemeral=True)
                result = await dispatch_purge(
                    self._moderation_dispatcher,
                    user_id=confirm_interaction.user.id,
                    guild_id=confirm_interaction.guild.id,
                    channel_id=confirm_interaction.channel_id,
                    amount=amount,
                    target_user_id=user.id if user else None,
                    hours=hours,
                    confirmed=True,
                    interaction=confirm_interaction,
                )
                await confirm_interaction.followup.send(
                    f"✅ **{result.value['deleted']}件** 削除したで。",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await confirm_interaction.followup.send(
                    "メッセージを削除する権限が茜にないみたいや。",
                    ephemeral=True,
                )
            except Exception as exc:
                logger.exception("Purge capability failed: %s", exc)
                await confirm_interaction.followup.send("メッセージ削除中にエラーが起きたで。", ephemeral=True)

        await interaction.response.send_message(
            f"⚠️ 最大 **{amount}件** のメッセージを削除する？{target_text}{hours_text}\n確定するまで削除せえへんで。",
            view=AdminConfirmView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label="削除を確定",
            ),
            ephemeral=True,
        )
