from __future__ import annotations

import logging

import discord

from discord import app_commands

from config import Config
from cogs.general_commands import GeneralCog as LegacyGeneralCog
from services.user_capabilities import (
    build_user_capability_dispatcher,
    dispatch_memory_forget,
    dispatch_memory_status,
    dispatch_remind,
    dispatch_title_set,
    dispatch_titles,
)


logger = logging.getLogger("AkaneBot")


class GeneralCog(LegacyGeneralCog):
    """Release C strangler layer for migrated general capabilities.

    Unmigrated commands continue to inherit their production behavior from
    ``LegacyGeneralCog``. Migrated commands override only the data/domain path;
    Discord presentation and user-visible compatibility remain explicit here.
    """

    def __init__(self, bot):
        super().__init__(bot)
        self._user_capability_dispatcher = build_user_capability_dispatcher(
            getattr(bot, "db", None)
        )

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
            await dispatch_remind(
                self._user_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=(
                    interaction.guild.id
                    if interaction.guild
                    else None
                ),
                channel_id=interaction.channel.id,
                minutes=minutes,
                message=message,
                # A direct slash command is already an explicit user action.
                confirmed=True,
            )
            await interaction.response.send_message(
                f"⏰ {minutes}分後に"
                f"「{message}」って知らせるで！",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"/remind failed: {e}")
            await interaction.response.send_message(
                "リマインダー登録中にエラーが起きたで。",
                ephemeral=True
            )

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
            result = await dispatch_memory_status(
                self._user_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
            )
            count = result.value["count"]
            active_count = min(count, Config.MEMORY_MESSAGE_LIMIT)

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🧠 茜の会話メモリー",
                    description=(
                        f"保存履歴: **{count}件**\n"
                        f"参照最大: **{active_count}件**\n"
                        f"保存期間: **{Config.MEMORY_RETENTION_DAYS}日**"
                    ),
                    color=discord.Color.purple()
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"/memory failed: {e}")
            await interaction.response.send_message(
                "記憶情報を確認できへんかったわ。",
                ephemeral=True
            )

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
            result = await dispatch_memory_forget(
                self._user_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                all_channels=all_channels,
                # Direct slash invocation preserves the legacy explicit action.
                confirmed=True,
            )
            deleted = result.value["deleted"]
            await interaction.response.send_message(
                f"🧹 **{deleted}件** 消したで！",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"/forget failed: {e}")
            await interaction.response.send_message(
                "履歴削除中にエラーが起きたで。",
                ephemeral=True
            )

    @app_commands.command(
        name="titles",
        description="獲得済み称号を表示"
    )
    async def titles(
        self,
        interaction: discord.Interaction
    ):
        try:
            result = await dispatch_titles(
                self._user_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel_id,
            )
            rows = result.value["rows"]

            if not rows:
                await interaction.response.send_message(
                    "まだ称号を持ってへんで。",
                    ephemeral=True
                )
                return

            lines = []
            for title_key, equipped, unlocked_at in rows:
                data = Config.TITLES.get(title_key)
                if not data:
                    continue
                marker = " 👈 **装備中**" if equipped else ""
                lines.append(
                    f"`{title_key}` {data['name']}{marker}\n"
                    f"　{data['description']}"
                )

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="🎖️ 獲得済み称号",
                    description="\n\n".join(lines),
                    color=discord.Color.blurple()
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"/titles failed: {e}")
            await interaction.response.send_message(
                "称号一覧を取得できへんかったわ。",
                ephemeral=True
            )

    @app_commands.command(
        name="title_set",
        description="プロフィールの称号を変更"
    )
    async def title_set(
        self,
        interaction: discord.Interaction,
        title_key: str
    ):
        title_key = title_key.strip().lower()

        try:
            if title_key not in Config.TITLES:
                await interaction.response.send_message(
                    "その称号キーは存在せえへんで。",
                    ephemeral=True
                )
                return

            result = await dispatch_title_set(
                self._user_capability_dispatcher,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel_id,
                title_key=title_key,
                # Direct slash invocation is explicit; natural-language paths
                # must separately satisfy the confirmation contract.
                confirmed=True,
            )

            if not result.ok:
                await interaction.response.send_message(
                    "その称号はまだ持ってへんで。",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                (
                    "🎖️ 表示称号を "
                    f"**{Config.TITLES[title_key]['name']}** "
                    "に変更したで！"
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"/title_set failed: {e}")
            await interaction.response.send_message(
                "称号変更中にエラーが起きたで。",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
