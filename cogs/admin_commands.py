import logging

from datetime import datetime, timedelta
from typing import Optional

import discord
import pytz

from discord import app_commands

from config import Config
from views.ticket_view import TicketView


logger = logging.getLogger("AkaneBot")


class AdminCommands(app_commands.Group):

    def __init__(self, bot):

        super().__init__(
            name="admin",
            description="サーバー管理コマンド"
        )

        self.bot = bot

    # ==========================================================================
    # 管理者権限チェック
    # ==========================================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:

        if interaction.guild is None:

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "このコマンドはサーバー内専用やで。",
                    ephemeral=True
                )

            return False

        if not interaction.user.guild_permissions.administrator:

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "⛔ このコマンドは管理者専用やで！",
                    ephemeral=True
                )

            return False

        return True

    # ==========================================================================
    # Admin Status - V31
    # ==========================================================================

    @app_commands.command(
        name="status",
        description="現在の茜Botサーバー設定を確認"
    )
    async def status(
        self,
        interaction: discord.Interaction
    ):

        try:

            guild_id = interaction.guild.id

            # ==================================================================
            # Channel Config
            # ==================================================================

            welcome_id = await self.bot.db.get_config(
                guild_id,
                "welcome_ch"
            )

            log_id = await self.bot.db.get_config(
                guild_id,
                "log_ch"
            )

            starboard_id = await self.bot.db.get_config(
                guild_id,
                "starboard_ch"
            )

            auto_chat_id = await self.bot.db.get_config(
                guild_id,
                "auto_chat_ch"
            )

            # ==================================================================
            # Counts
            # ==================================================================

            ng_row = await self.bot.db._fetchone(
                """
                SELECT COUNT(*)
                FROM ng_words
                WHERE guild_id=?
                """,
                (
                    guild_id,
                )
            )

            response_row = await self.bot.db._fetchone(
                """
                SELECT COUNT(*)
                FROM auto_replies
                WHERE guild_id=?
                """,
                (
                    guild_id,
                )
            )

            reward_row = await self.bot.db._fetchone(
                """
                SELECT COUNT(*)
                FROM level_rewards
                WHERE guild_id=?
                """,
                (
                    guild_id,
                )
            )

            monthly_row = await self.bot.db._fetchone(
                """
                SELECT
                    rule_ch,
                    target_ch
                FROM monthly_rules
                WHERE guild_id=?
                """,
                (
                    guild_id,
                )
            )

            open_tickets = await self.bot.db.count_open_tickets(
                guild_id
            )

            ng_count = (
                int(ng_row[0])
                if ng_row
                else 0
            )

            response_count = (
                int(response_row[0])
                if response_row
                else 0
            )

            reward_count = (
                int(reward_row[0])
                if reward_row
                else 0
            )

            # ==================================================================
            # Channel Helper
            # ==================================================================

            def channel_text(channel_id):

                if not channel_id:

                    return "❌ 未設定"

                channel = interaction.guild.get_channel(
                    channel_id
                )

                if channel:

                    return f"✅ {channel.mention}"

                return (
                    "⚠️ 不明なチャンネル "
                    f"(`{channel_id}`)"
                )

            # ==================================================================
            # Monthly
            # ==================================================================

            if monthly_row:

                rule_channel_id = monthly_row[0]
                target_channel_id = monthly_row[1]

                monthly_text = (
                    "✅ 設定済み\n"
                    f"ルール: {channel_text(rule_channel_id)}\n"
                    f"通知先: {channel_text(target_channel_id)}"
                )

            else:

                monthly_text = "❌ 未設定"

            # ==================================================================
            # Embed
            # ==================================================================

            embed = discord.Embed(
                title="🌸 茜Bot サーバー設定",
                description=(
                    f"**{interaction.guild.name}** "
                    "の現在設定やで。"
                ),
                color=discord.Color.red()
            )

            embed.add_field(
                name="👋 Welcome",
                value=channel_text(
                    welcome_id
                ),
                inline=False
            )

            embed.add_field(
                name="📝 監査ログ",
                value=channel_text(
                    log_id
                ),
                inline=False
            )

            embed.add_field(
                name="❤️ Starboard",
                value=channel_text(
                    starboard_id
                ),
                inline=False
            )

            embed.add_field(
                name="🤖 AI常駐チャンネル",
                value=channel_text(
                    auto_chat_id
                ),
                inline=False
            )

            embed.add_field(
                name="🚫 NGワード",
                value=f"**{ng_count}件**",
                inline=True
            )

            embed.add_field(
                name="💬 自動応答",
                value=f"**{response_count}件**",
                inline=True
            )

            embed.add_field(
                name="🎁 レベル報酬",
                value=f"**{reward_count}件**",
                inline=True
            )

            embed.add_field(
                name="📩 Open Ticket",
                value=f"**{open_tickets}件**",
                inline=True
            )

            embed.add_field(
                name="📅 月次通知",
                value=monthly_text,
                inline=False
            )

            embed.add_field(
                name="🧠 AI",
                value=(
                    f"通常: `{Config.CHAT_MODEL}`\n"
                    f"高推論: `{Config.REASONING_MODEL}`\n"
                    f"高速: `{Config.FAST_MODEL}`"
                ),
                inline=False
            )

            embed.add_field(
                name="✨ XP",
                value=(
                    f"1回: **{Config.XP_PER_MESSAGE} XP**\n"
                    f"クールダウン: "
                    f"**{Config.XP_COOLDOWN_SECONDS}秒**"
                ),
                inline=False
            )

            embed.add_field(
                name="🛡️ Spam Protection",
                value=(
                    f"{Config.SPAM_WINDOW_SECONDS}秒以内に "
                    f"{Config.SPAM_MESSAGE_THRESHOLD}投稿\n"
                    f"同文: "
                    f"{Config.DUPLICATE_MESSAGE_THRESHOLD}連投\n"
                    f"大量メンション: "
                    f"{Config.MASS_MENTION_THRESHOLD}人以上\n"
                    "Strike 1: 警告\n"
                    f"Strike 2: "
                    f"{Config.SPAM_TIMEOUT_1_SECONDS}秒 Timeout\n"
                    f"Strike 3: "
                    f"{Config.SPAM_TIMEOUT_2_SECONDS}秒 Timeout\n"
                    f"Strike 4+: "
                    f"{Config.SPAM_TIMEOUT_3_SECONDS}秒 Timeout"
                ),
                inline=False
            )

            embed.add_field(
                name="💾 Database",
                value=f"`{Config.DB_NAME}`",
                inline=False
            )

            embed.set_footer(
                text="Akane Bot v31"
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"/admin status failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "設定情報の取得中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Config Log
    # ==========================================================================

    @app_commands.command(
        name="config_log",
        description="監査ログ設定"
    )
    async def config_log(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        try:

            await self.bot.db.set_config(
                interaction.guild.id,
                "log_ch",
                channel.id
            )

            await interaction.response.send_message(
                f"✅ ログ出力先を "
                f"{channel.mention} に設定したで。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"config_log failed: {e}"
            )

            await interaction.response.send_message(
                "ログ設定中にエラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Config Welcome
    # ==========================================================================

    @app_commands.command(
        name="config_welcome",
        description="挨拶設定"
    )
    async def config_welcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        try:

            await self.bot.db.set_config(
                interaction.guild.id,
                "welcome_ch",
                channel.id
            )

            await interaction.response.send_message(
                f"✅ 挨拶場所を "
                f"{channel.mention} に設定したで。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"config_welcome failed: {e}"
            )

            await interaction.response.send_message(
                "挨拶設定中にエラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Config Starboard
    # ==========================================================================

    @app_commands.command(
        name="config_starboard",
        description="殿堂入り設定"
    )
    async def config_starboard(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        try:

            await self.bot.db.set_config(
                interaction.guild.id,
                "starboard_ch",
                channel.id
            )

            await interaction.response.send_message(
                f"✅ 殿堂入り先を "
                f"{channel.mention} に設定したで。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"config_starboard failed: {e}"
            )

            await interaction.response.send_message(
                "Starboard設定中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Config Auto Chat
    # ==========================================================================

    @app_commands.command(
        name="config_autochat",
        description="常駐チャット設定"
    )
    async def config_autochat(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        try:

            await self.bot.db.set_config(
                interaction.guild.id,
                "auto_chat_ch",
                channel.id
            )

            await interaction.response.send_message(
                f"✅ AI常駐場所を "
                f"{channel.mention} に設定したで。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"config_autochat failed: {e}"
            )

            await interaction.response.send_message(
                "AI常駐設定中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Config Monthly
    # ==========================================================================

    @app_commands.command(
        name="config_monthly",
        description="月次ルール通知設定"
    )
    async def config_monthly(
        self,
        interaction: discord.Interaction,
        rule_ch: discord.TextChannel,
        target_ch: discord.TextChannel
    ):

        try:

            await self.bot.db._execute(
                """
                INSERT OR REPLACE
                INTO monthly_rules
                (
                    guild_id,
                    rule_ch,
                    target_ch
                )
                VALUES (?, ?, ?)
                """,
                (
                    interaction.guild.id,
                    rule_ch.id,
                    target_ch.id
                )
            )

            await interaction.response.send_message(
                "✅ 月次通知を設定したで。\n"
                f"ルール: {rule_ch.mention}\n"
                f"通知先: {target_ch.mention}",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"config_monthly failed: {e}"
            )

            await interaction.response.send_message(
                "月次通知設定中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Setup Ticket - V31
    # ==========================================================================

    @app_commands.command(
        name="setup_ticket",
        description="Ticketパネル設置"
    )
    async def setup_ticket(
        self,
        interaction: discord.Interaction
    ):

        try:

            embed = discord.Embed(
                title="📩 サポート・問い合わせ",
                description=(
                    "問い合わせがある人は、"
                    "下のメニューから種類を選んでな。\n\n"
                    "専用の非公開チャンネルを作るで！"
                ),
                color=discord.Color.blue()
            )

            embed.add_field(
                name="🛡️ 管理者への相談",
                value="管理者に直接相談したいとき",
                inline=False
            )

            embed.add_field(
                name="🤖 Botの不具合",
                value="茜Botのエラーや不具合",
                inline=False
            )

            embed.add_field(
                name="💬 サーバーについて",
                value="ルールや運営について",
                inline=False
            )

            embed.add_field(
                name="📦 その他",
                value="それ以外の問い合わせ",
                inline=False
            )

            embed.set_footer(
                text=(
                    "1人につき同時に"
                    "1つのTicketまで"
                )
            )

            await interaction.channel.send(
                embed=embed,
                view=TicketView(
                    self.bot
                )
            )

            await interaction.response.send_message(
                "✅ Ticketパネルを設置したで。",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "Ticketパネルを設置する"
                "権限が茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Ticket panel setup failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Ticket設置中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Reaction Role
    # ==========================================================================

    @app_commands.command(
        name="rolepanel",
        description="ロールパネル作成"
    )
    @app_commands.describe(
        message_id="対象メッセージID",
        emoji="使用する絵文字",
        role="付与するロール"
    )
    async def rolepanel(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role
    ):

        try:

            message = await interaction.channel.fetch_message(
                int(message_id)
            )

            await message.add_reaction(
                emoji
            )

            await self.bot.db._execute(
                """
                INSERT INTO reaction_roles
                (
                    message_id,
                    emoji,
                    role_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    message.id,
                    emoji,
                    role.id
                )
            )

            await interaction.response.send_message(
                "✅ リアクションロールを設定したで。\n"
                f"絵文字: {emoji}\n"
                f"ロール: {role.mention}",
                ephemeral=True
            )

        except ValueError:

            await interaction.response.send_message(
                "メッセージIDは数字で指定してな！",
                ephemeral=True
            )

        except discord.NotFound:

            await interaction.response.send_message(
                "そのメッセージが見つからへんかったで。",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "茜に必要な権限がないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Role panel setup failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "リアクションロール設定中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Level Reward
    # ==========================================================================

    @app_commands.command(
        name="level_reward",
        description="レベル報酬設定"
    )
    async def level_reward(
        self,
        interaction: discord.Interaction,
        level: int,
        role: discord.Role
    ):

        if level < 1:

            await interaction.response.send_message(
                "レベルは1以上にしてな。",
                ephemeral=True
            )

            return

        try:

            await self.bot.db._execute(
                """
                INSERT OR REPLACE
                INTO level_rewards
                (
                    guild_id,
                    level,
                    role_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    interaction.guild.id,
                    level,
                    role.id
                )
            )

            await interaction.response.send_message(
                f"✅ **Lv.{level}** で "
                f"{role.mention} を付与する設定にしたで！",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"level_reward failed: {e}"
            )

            await interaction.response.send_message(
                "レベル報酬設定中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Level Reward Remove
    # ==========================================================================

    @app_commands.command(
        name="level_reward_remove",
        description="レベル報酬削除"
    )
    async def level_reward_remove(
        self,
        interaction: discord.Interaction,
        level: int
    ):

        try:

            await self.bot.db._execute(
                """
                DELETE FROM level_rewards
                WHERE guild_id=?
                AND level=?
                """,
                (
                    interaction.guild.id,
                    level
                )
            )

            await interaction.response.send_message(
                f"✅ Lv.{level} の"
                "報酬設定を削除したで。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"level_reward_remove failed: {e}"
            )

            await interaction.response.send_message(
                "レベル報酬削除中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Level Reward List
    # ==========================================================================

    @app_commands.command(
        name="level_reward_list",
        description="レベル報酬一覧"
    )
    async def level_reward_list(
        self,
        interaction: discord.Interaction
    ):

        try:

            rows = await self.bot.db._fetchall(
                """
                SELECT
                    level,
                    role_id
                FROM level_rewards
                WHERE guild_id=?
                ORDER BY level ASC
                """,
                (
                    interaction.guild.id,
                )
            )

            if not rows:

                await interaction.response.send_message(
                    "レベル報酬は"
                    "まだ設定されてへんで。",
                    ephemeral=True
                )

                return

            lines = []

            for (
                level_value,
                role_id
            ) in rows:

                role = interaction.guild.get_role(
                    role_id
                )

                role_text = (
                    role.mention
                    if role
                    else (
                        "⚠️ 削除済みロール "
                        f"(`{role_id}`)"
                    )
                )

                lines.append(
                    f"**Lv.{level_value}**"
                    f" → {role_text}"
                )

            embed = discord.Embed(
                title="🎁 レベル報酬一覧",
                description="\n".join(
                    lines
                ),
                color=discord.Color.gold()
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"level_reward_list failed: {e}"
            )

            await interaction.response.send_message(
                "レベル報酬一覧の取得中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # NG Word Add
    # ==========================================================================

    @app_commands.command(
        name="filter_add",
        description="NGワード追加"
    )
    async def filter_add(
        self,
        interaction: discord.Interaction,
        word: str
    ):

        word = word.strip()

        if not word:

            await interaction.response.send_message(
                "NGワードを入力してな。",
                ephemeral=True
            )

            return

        try:

            exists = await self.bot.db._fetchone(
                """
                SELECT 1
                FROM ng_words
                WHERE guild_id=?
                AND word=?
                LIMIT 1
                """,
                (
                    interaction.guild.id,
                    word
                )
            )

            if exists:

                await interaction.response.send_message(
                    f"`{word}` は"
                    "もう登録されてるで。",
                    ephemeral=True
                )

                return

            await self.bot.db._execute(
                """
                INSERT INTO ng_words
                (
                    guild_id,
                    word
                )
                VALUES (?, ?)
                """,
                (
                    interaction.guild.id,
                    word
                )
            )

            await interaction.response.send_message(
                f"✅ NGワード追加: `{word}`",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"filter_add failed: {e}"
            )

            await interaction.response.send_message(
                "NGワード追加中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Auto Response Add
    # ==========================================================================

    @app_commands.command(
        name="response_add",
        description="自動応答追加"
    )
    async def response_add(
        self,
        interaction: discord.Interaction,
        trigger: str,
        response: str
    ):

        trigger = trigger.strip()
        response = response.strip()

        if not trigger or not response:

            await interaction.response.send_message(
                "トリガーと応答文の"
                "両方を入力してな。",
                ephemeral=True
            )

            return

        try:

            await self.bot.db._execute(
                """
                INSERT INTO auto_replies
                (
                    guild_id,
                    trigger,
                    response
                )
                VALUES (?, ?, ?)
                """,
                (
                    interaction.guild.id,
                    trigger,
                    response
                )
            )

            await interaction.response.send_message(
                "✅ 自動応答を追加したで。\n"
                f"**トリガー:** `{trigger}`\n"
                f"**応答:** {response}",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"response_add failed: {e}"
            )

            await interaction.response.send_message(
                "自動応答追加中に"
                "エラーが起きたで。",
                ephemeral=True
            )

    # ==========================================================================
    # Kick
    # ==========================================================================

    @app_commands.command(
        name="kick",
        description="メンバーをKick"
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if member.id == interaction.user.id:

            await interaction.response.send_message(
                "自分自身をKickするんは"
                "やめとき！",
                ephemeral=True
            )

            return

        if (
            self.bot.user
            and member.id == self.bot.user.id
        ):

            await interaction.response.send_message(
                "茜自身はKickできへんで！",
                ephemeral=True
            )

            return

        try:

            await member.kick(
                reason=(
                    f"Executed by "
                    f"{interaction.user} "
                    f"via Akane Bot"
                )
            )

            await interaction.response.send_message(
                f"✅ **{member}** をKickしたで。",
                ephemeral=True
            )

            logger.info(
                "Member kicked | "
                f"guild={interaction.guild.id} | "
                f"target={member.id} | "
                f"admin={interaction.user.id}"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "そのメンバーをKickする"
                "権限が茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Kick failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Kick処理中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Ban
    # ==========================================================================

    @app_commands.command(
        name="ban",
        description="メンバーをBan"
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if member.id == interaction.user.id:

            await interaction.response.send_message(
                "自分自身をBanするんは"
                "やめとき！",
                ephemeral=True
            )

            return

        if (
            self.bot.user
            and member.id == self.bot.user.id
        ):

            await interaction.response.send_message(
                "茜自身はBanできへんで！",
                ephemeral=True
            )

            return

        try:

            await member.ban(
                reason=(
                    f"Executed by "
                    f"{interaction.user} "
                    f"via Akane Bot"
                )
            )

            await interaction.response.send_message(
                f"✅ **{member}** をBanしたで。",
                ephemeral=True
            )

            logger.info(
                "Member banned | "
                f"guild={interaction.guild.id} | "
                f"target={member.id} | "
                f"admin={interaction.user.id}"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "そのメンバーをBanする"
                "権限が茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Ban failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "Ban処理中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Purge
    # ==========================================================================

    @app_commands.command(
        name="purge",
        description="メッセージ削除"
    )
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: Optional[discord.Member] = None,
        hours: Optional[int] = None
    ):

        if amount < 1:

            await interaction.response.send_message(
                "削除数は1以上にしてな。",
                ephemeral=True
            )

            return

        if amount > 300:

            amount = 300

        if (
            hours is not None
            and hours < 1
        ):

            await interaction.response.send_message(
                "時間指定は1時間以上にしてな。",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        cutoff = (
            datetime.now(
                pytz.utc
            )
            - timedelta(
                hours=hours
            )
            if hours
            else None
        )

        def check(message):

            if (
                user
                and message.author != user
            ):

                return False

            if (
                cutoff
                and message.created_at < cutoff
            ):

                return False

            return True

        try:

            deleted = await interaction.channel.purge(
                limit=amount,
                check=check
            )

            await interaction.followup.send(
                f"✅ **{len(deleted)}件** "
                "削除したで。",
                ephemeral=True
            )

            logger.info(
                "Messages purged | "
                f"guild={interaction.guild.id} | "
                f"channel={interaction.channel.id} | "
                f"count={len(deleted)} | "
                f"admin={interaction.user.id}"
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "メッセージを削除する"
                "権限が茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Purge failed: {e}"
            )

            await interaction.followup.send(
                "メッセージ削除中に"
                "エラーが起きたで。",
                ephemeral=True
            )


# ==============================================================================
# Extension Setup
# ==============================================================================

async def setup(bot):

    bot.tree.add_command(
        AdminCommands(bot)
    )
