from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz
from discord import app_commands

from cogs.admin_commands import AdminCommands as LegacyAdminCommands
from services.admin_capabilities import (
    CONFIG_AUTOCHAT_SPEC,
    CONFIG_LOG_SPEC,
    CONFIG_MONTHLY_SPEC,
    CONFIG_STARBOARD_SPEC,
    CONFIG_WELCOME_SPEC,
    FILTER_ADD_SPEC,
    LEVEL_REWARD_REMOVE_SPEC,
    LEVEL_REWARD_SPEC,
    RESPONSE_ADD_SPEC,
    ROLEPANEL_SPEC,
    SETUP_TICKET_SPEC,
    build_admin_capability_dispatcher,
    dispatch_admin_action,
)
from services.moderation_capabilities import (
    build_moderation_capability_dispatcher,
    dispatch_ban,
    dispatch_kick,
    dispatch_purge,
)
from views.admin_confirm_view import AdminConfirmView
from views.ticket_view import TicketView


logger = logging.getLogger("AkaneBot")


class AdminCommands(LegacyAdminCommands):
    """Stable admin runtime with fail-closed ADMIN/MODERATION execution."""

    def __init__(self, bot):
        super().__init__(bot)
        self._moderation_dispatcher = build_moderation_capability_dispatcher(self)
        self._admin_dispatcher = build_admin_capability_dispatcher(self)

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

    async def _prompt_admin_action(
        self,
        interaction: discord.Interaction,
        *,
        capability_id: str,
        arguments: dict,
        review_text: str,
        confirm_label: str,
        success_text,
    ) -> None:
        if not await self._require_admin(interaction):
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            try:
                result = await dispatch_admin_action(
                    self._admin_dispatcher,
                    capability_id=capability_id,
                    user_id=confirm_interaction.user.id,
                    guild_id=confirm_interaction.guild.id,
                    channel_id=confirm_interaction.channel_id,
                    arguments=arguments,
                    confirmed=True,
                    interaction=confirm_interaction,
                )
                text = success_text(result.value)
                await confirm_interaction.response.edit_message(content=text, view=None)
            except discord.NotFound:
                await confirm_interaction.response.send_message(
                    "対象が見つからへんかったで。設定は変更してへんで。",
                    ephemeral=True,
                )
            except discord.Forbidden:
                await confirm_interaction.response.send_message(
                    "茜に必要な権限がないみたいや。設定は変更してへんで。",
                    ephemeral=True,
                )
            except Exception as exc:
                logger.exception("Admin capability failed | capability=%s | error=%s", capability_id, exc)
                if not confirm_interaction.response.is_done():
                    await confirm_interaction.response.send_message(
                        "管理設定の処理中にエラーが起きたで。",
                        ephemeral=True,
                    )

        await interaction.response.send_message(
            review_text + "\n確定するまで変更はせえへんで。",
            view=AdminConfirmView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label=confirm_label,
            ),
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # Moderation data source
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Admin data source
    # ------------------------------------------------------------------
    async def perform_admin_action(self, *, context, capability_id: str, arguments):
        interaction = context.interaction
        guild = interaction.guild
        if guild is None:
            raise ValueError("guild_required")

        value = {}
        config_map = {
            CONFIG_LOG_SPEC.capability_id: "log_ch",
            CONFIG_WELCOME_SPEC.capability_id: "welcome_ch",
            CONFIG_STARBOARD_SPEC.capability_id: "starboard_ch",
            CONFIG_AUTOCHAT_SPEC.capability_id: "auto_chat_ch",
        }

        if capability_id in config_map:
            channel_id = int(arguments["channel_id"])
            await self.bot.db.set_config(guild.id, config_map[capability_id], channel_id)
            value = {"channel_id": channel_id}
        elif capability_id == CONFIG_MONTHLY_SPEC.capability_id:
            rule_ch_id = int(arguments["rule_ch_id"])
            target_ch_id = int(arguments["target_ch_id"])
            await self.bot.db._execute(
                "INSERT OR REPLACE INTO monthly_rules (guild_id, rule_ch, target_ch) VALUES (?, ?, ?)",
                (guild.id, rule_ch_id, target_ch_id),
            )
            value = {"rule_ch_id": rule_ch_id, "target_ch_id": target_ch_id}
        elif capability_id == SETUP_TICKET_SPEC.capability_id:
            embed = discord.Embed(
                title="📩 サポート・問い合わせ",
                description="問い合わせがある人は、下のメニューから種類を選んでな。\n\n専用の非公開チャンネルを作るで！",
                color=discord.Color.blue(),
            )
            embed.add_field(name="🛡️ 管理者への相談", value="管理者に直接相談したいとき", inline=False)
            embed.add_field(name="🤖 Botの不具合", value="茜Botのエラーや不具合", inline=False)
            embed.add_field(name="💬 サーバーについて", value="ルールや運営について", inline=False)
            embed.add_field(name="📦 その他", value="それ以外の問い合わせ", inline=False)
            embed.set_footer(text="1人につき同時に1つのTicketまで")
            await interaction.channel.send(embed=embed, view=TicketView(self.bot))
            value = {"channel_id": interaction.channel.id}
        elif capability_id == ROLEPANEL_SPEC.capability_id:
            message = await interaction.channel.fetch_message(int(arguments["message_id"]))
            role = guild.get_role(int(arguments["role_id"]))
            if role is None:
                raise ValueError("role_missing")
            emoji = str(arguments["emoji"])
            await message.add_reaction(emoji)
            await self.bot.db._execute(
                "INSERT INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)",
                (message.id, emoji, role.id),
            )
            value = {"message_id": message.id, "emoji": emoji, "role_id": role.id}
        elif capability_id == LEVEL_REWARD_SPEC.capability_id:
            level = int(arguments["level"])
            role_id = int(arguments["role_id"])
            await self.bot.db._execute(
                "INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)",
                (guild.id, level, role_id),
            )
            value = {"level": level, "role_id": role_id}
        elif capability_id == LEVEL_REWARD_REMOVE_SPEC.capability_id:
            level = int(arguments["level"])
            await self.bot.db._execute(
                "DELETE FROM level_rewards WHERE guild_id=? AND level=?",
                (guild.id, level),
            )
            value = {"level": level}
        elif capability_id == FILTER_ADD_SPEC.capability_id:
            word = str(arguments["word"])
            exists = await self.bot.db._fetchone(
                "SELECT 1 FROM ng_words WHERE guild_id=? AND word=? LIMIT 1",
                (guild.id, word),
            )
            if exists:
                value = {"word": word, "already_exists": True}
            else:
                await self.bot.db._execute(
                    "INSERT INTO ng_words (guild_id, word) VALUES (?, ?)",
                    (guild.id, word),
                )
                value = {"word": word, "already_exists": False}
        elif capability_id == RESPONSE_ADD_SPEC.capability_id:
            trigger = str(arguments["trigger"])
            response = str(arguments["response"])
            await self.bot.db._execute(
                "INSERT INTO auto_replies (guild_id, trigger, response) VALUES (?, ?, ?)",
                (guild.id, trigger, response),
            )
            value = {"trigger": trigger, "response": response}
        else:
            raise ValueError(f"unsupported_admin_capability:{capability_id}")

        logger.info(
            "Admin capability executed | action=%s | guild=%s | admin=%s",
            capability_id,
            guild.id,
            interaction.user.id,
        )
        return value

    # ------------------------------------------------------------------
    # ADMIN configuration commands
    # ------------------------------------------------------------------
    @app_commands.command(name="config_log", description="監査ログ設定")
    async def config_log(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._prompt_admin_action(
            interaction,
            capability_id=CONFIG_LOG_SPEC.capability_id,
            arguments={"channel_id": channel.id},
            review_text=f"📝 監査ログ出力先を {channel.mention} に変更する？",
            confirm_label="ログ設定を確定",
            success_text=lambda value: f"✅ ログ出力先を <#{value['channel_id']}> に設定したで。",
        )

    @app_commands.command(name="config_welcome", description="挨拶設定")
    async def config_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._prompt_admin_action(
            interaction,
            capability_id=CONFIG_WELCOME_SPEC.capability_id,
            arguments={"channel_id": channel.id},
            review_text=f"👋 挨拶場所を {channel.mention} に変更する？",
            confirm_label="挨拶設定を確定",
            success_text=lambda value: f"✅ 挨拶場所を <#{value['channel_id']}> に設定したで。",
        )

    @app_commands.command(name="config_starboard", description="殿堂入り設定")
    async def config_starboard(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._prompt_admin_action(
            interaction,
            capability_id=CONFIG_STARBOARD_SPEC.capability_id,
            arguments={"channel_id": channel.id},
            review_text=f"❤️ 殿堂入り先を {channel.mention} に変更する？",
            confirm_label="殿堂入り設定を確定",
            success_text=lambda value: f"✅ 殿堂入り先を <#{value['channel_id']}> に設定したで。",
        )

    @app_commands.command(name="config_autochat", description="常駐チャット設定")
    async def config_autochat(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._prompt_admin_action(
            interaction,
            capability_id=CONFIG_AUTOCHAT_SPEC.capability_id,
            arguments={"channel_id": channel.id},
            review_text=f"🤖 AI常駐場所を {channel.mention} に変更する？",
            confirm_label="常駐設定を確定",
            success_text=lambda value: f"✅ AI常駐場所を <#{value['channel_id']}> に設定したで。",
        )

    @app_commands.command(name="config_monthly", description="月次ルール通知設定")
    async def config_monthly(self, interaction: discord.Interaction, rule_ch: discord.TextChannel, target_ch: discord.TextChannel):
        await self._prompt_admin_action(
            interaction,
            capability_id=CONFIG_MONTHLY_SPEC.capability_id,
            arguments={"rule_ch_id": rule_ch.id, "target_ch_id": target_ch.id},
            review_text=f"📅 月次通知を設定する？\nルール: {rule_ch.mention}\n通知先: {target_ch.mention}",
            confirm_label="月次設定を確定",
            success_text=lambda value: f"✅ 月次通知を設定したで。\nルール: <#{value['rule_ch_id']}>\n通知先: <#{value['target_ch_id']}>",
        )

    @app_commands.command(name="setup_ticket", description="Ticketパネル設置")
    async def setup_ticket(self, interaction: discord.Interaction):
        await self._prompt_admin_action(
            interaction,
            capability_id=SETUP_TICKET_SPEC.capability_id,
            arguments={},
            review_text=f"📩 {interaction.channel.mention} にTicketパネルを設置する？",
            confirm_label="Ticket設置を確定",
            success_text=lambda value: f"✅ <#{value['channel_id']}> にTicketパネルを設置したで。",
        )

    @app_commands.command(name="rolepanel", description="ロールパネル作成")
    @app_commands.describe(message_id="対象メッセージID", emoji="使用する絵文字", role="付与するロール")
    async def rolepanel(self, interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
        try:
            normalized_message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("メッセージIDは数字で指定してな！", ephemeral=True)
            return
        await self._prompt_admin_action(
            interaction,
            capability_id=ROLEPANEL_SPEC.capability_id,
            arguments={"message_id": normalized_message_id, "emoji": emoji, "role_id": role.id},
            review_text=f"🎭 メッセージ `{normalized_message_id}` に {emoji} → {role.mention} のリアクションロールを設定する？",
            confirm_label="ロール設定を確定",
            success_text=lambda value: f"✅ リアクションロールを設定したで。\n絵文字: {value['emoji']}\nロール: <@&{value['role_id']}>",
        )

    @app_commands.command(name="level_reward", description="レベル報酬設定")
    async def level_reward(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if level < 1:
            await interaction.response.send_message("レベルは1以上にしてな。", ephemeral=True)
            return
        await self._prompt_admin_action(
            interaction,
            capability_id=LEVEL_REWARD_SPEC.capability_id,
            arguments={"level": level, "role_id": role.id},
            review_text=f"🎁 Lv.{level} の報酬を {role.mention} に設定する？",
            confirm_label="報酬設定を確定",
            success_text=lambda value: f"✅ **Lv.{value['level']}** で <@&{value['role_id']}> を付与する設定にしたで！",
        )

    @app_commands.command(name="level_reward_remove", description="レベル報酬削除")
    async def level_reward_remove(self, interaction: discord.Interaction, level: int):
        if level < 1:
            await interaction.response.send_message("レベルは1以上にしてな。", ephemeral=True)
            return
        await self._prompt_admin_action(
            interaction,
            capability_id=LEVEL_REWARD_REMOVE_SPEC.capability_id,
            arguments={"level": level},
            review_text=f"🗑️ Lv.{level} の報酬設定を削除する？",
            confirm_label="報酬削除を確定",
            success_text=lambda value: f"✅ Lv.{value['level']} の報酬設定を削除したで。",
        )

    @app_commands.command(name="filter_add", description="NGワード追加")
    async def filter_add(self, interaction: discord.Interaction, word: str):
        word = word.strip()
        if not word:
            await interaction.response.send_message("NGワードを入力してな。", ephemeral=True)
            return
        await self._prompt_admin_action(
            interaction,
            capability_id=FILTER_ADD_SPEC.capability_id,
            arguments={"word": word},
            review_text=f"🚫 NGワード `{word}` を追加する？",
            confirm_label="NGワード追加を確定",
            success_text=lambda value: (f"`{value['word']}` はもう登録されてるで。" if value['already_exists'] else f"✅ NGワード追加: `{value['word']}`"),
        )

    @app_commands.command(name="response_add", description="自動応答追加")
    async def response_add(self, interaction: discord.Interaction, trigger: str, response: str):
        trigger = trigger.strip()
        response = response.strip()
        if not trigger or not response:
            await interaction.response.send_message("トリガーと応答文の両方を入力してな。", ephemeral=True)
            return
        await self._prompt_admin_action(
            interaction,
            capability_id=RESPONSE_ADD_SPEC.capability_id,
            arguments={"trigger": trigger, "response": response},
            review_text=f"💬 自動応答を追加する？\nトリガー: `{trigger}`\n応答: {response}",
            confirm_label="自動応答追加を確定",
            success_text=lambda value: f"✅ 自動応答を追加したで。\n**トリガー:** `{value['trigger']}`\n**応答:** {value['response']}",
        )

    # ------------------------------------------------------------------
    # MODERATION commands
    # ------------------------------------------------------------------
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
