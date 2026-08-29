import logging
from typing import Optional

import discord
from discord import app_commands


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
    # 管理者チェック
    # ==========================================================================

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:

        if interaction.guild is None:

            await interaction.response.send_message(
                "このコマンドはサーバー内専用やで。",
                ephemeral=True
            )

            return False

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "⛔ このコマンドは管理者専用やで！",
                ephemeral=True
            )

            return False

        return True

    # ==========================================================================
    # Config
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

        await self.bot.db.set_config(
            interaction.guild.id,
            "log_ch",
            channel.id
        )

        await interaction.response.send_message(
            f"ログ出力先: {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="config_welcome",
        description="挨拶設定"
    )
    async def config_welcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        await self.bot.db.set_config(
            interaction.guild.id,
            "welcome_ch",
            channel.id
        )

        await interaction.response.send_message(
            f"挨拶場所: {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="config_starboard",
        description="殿堂入り設定"
    )
    async def config_starboard(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        await self.bot.db.set_config(
            interaction.guild.id,
            "starboard_ch",
            channel.id
        )

        await interaction.response.send_message(
            f"殿堂入り先: {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(
        name="config_autochat",
        description="常駐チャット設定"
    )
    async def config_autochat(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        await self.bot.db.set_config(
            interaction.guild.id,
            "auto_chat_ch",
            channel.id
        )

        await interaction.response.send_message(
            f"常駐場所: {channel.mention}",
            ephemeral=True
        )

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

        await self.bot.db._execute(
            """
            INSERT OR REPLACE INTO monthly_rules
            (guild_id, rule_ch, target_ch)
            VALUES (?, ?, ?)
            """,
            (
                interaction.guild.id,
                rule_ch.id,
                target_ch.id
            )
        )

        await interaction.response.send_message(
            "月次通知を設定したで。",
            ephemeral=True
        )

    # ==========================================================================
    # Ticket
    # ==========================================================================

    @app_commands.command(
        name="setup_ticket",
        description="チケット設置"
    )
    async def setup_ticket(
        self,
        interaction: discord.Interaction
    ):

        try:

            await interaction.channel.send(
                "📩 サポート窓口",
                view=TicketView()
            )

            await interaction.response.send_message(
                "設置完了",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Ticket panel setup failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "チケット設置中にエラーが起きたで。",
                    ephemeral=True
                )

    # ==========================================================================
    # Reaction Role
    # ==========================================================================

    @app_commands.command(
        name="rolepanel",
        description="ロールパネル作成"
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
                (message_id, emoji, role_id)
                VALUES (?, ?, ?)
                """,
                (
                    message.id,
                    emoji,
                    role.id
                )
            )

            await interaction.response.send_message(
                "✅ リアクションロールを設定したで。",
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
    # Level Rewards
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

        await self.bot.db._execute(
            """
            INSERT OR REPLACE INTO level_rewards
            (guild_id, level, role_id)
            VALUES (?, ?, ?)
            """,
            (
                interaction.guild.id,
                level,
                role.id
            )
        )

        await interaction.response.send_message(
            f"Lv.{level} で "
            f"{role.name} をあげる設定にしたで！",
            ephemeral=True
        )

    @app_commands.command(
        name="level_reward_remove",
        description="レベル報酬削除"
    )
    async def level_reward_remove(
        self,
        interaction: discord.Interaction,
        level: int
    ):

        await self.bot.db._execute(
            """
            DELETE FROM level_rewards
            WHERE guild_id=? AND level=?
            """,
            (
                interaction.guild.id,
                level
            )
        )

        await interaction.response.send_message(
            f"Lv.{level} の報酬設定を削除したで。",
            ephemeral=True
        )

    @app_commands.command(
        name="level_reward_list",
        description="レベル報酬一覧"
    )
    async def level_reward_list(
        self,
        interaction: discord.Interaction
    ):

        rows = await self.bot.db._fetchall(
            """
            SELECT level, role_id
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
                "設定なし。",
                ephemeral=True
            )

            return

        text = "\n".join(
            f"Lv.{level} -> <@&{role_id}>"
            for level, role_id in rows
        )

        await interaction.response.send_message(
            embed=discord.Embed(
                title="レベル報酬一覧",
                description=text
            ),
            ephemeral=True
        )

    # ==========================================================================
    # Filter / Response
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

        await self.bot.db._execute(
            """
            INSERT INTO ng_words
            (guild_id, word)
            VALUES (?, ?)
            """,
            (
                interaction.guild.id,
                word
            )
        )

        await interaction.response.send_message(
            f"NG追加: {word}",
            ephemeral=True
        )

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

        await self.bot.db._execute(
            """
            INSERT INTO auto_replies
            (guild_id, trigger, response)
            VALUES (?, ?, ?)
            """,
            (
                interaction.guild.id,
                trigger,
                response
            )
        )

        await interaction.response.send_message(
            f"応答追加: {trigger} -> {response}",
            ephemeral=True
        )

    # ==========================================================================
    # Kick / Ban
    # ==========================================================================

    @app_commands.command(
        name="kick",
        description="Kick"
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        try:

            await member.kick()

            await interaction.response.send_message(
                "Kick完了"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "そのメンバーをKickする権限が"
                "茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Kick failed: {e}"
            )

    @app_commands.command(
        name="ban",
        description="Ban"
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        try:

            await member.ban()

            await interaction.response.send_message(
                "Ban完了"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "そのメンバーをBanする権限が"
                "茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                f"Ban failed: {e}"
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

        await interaction.response.defer(
            ephemeral=True
        )

        from datetime import datetime, timedelta
        import pytz

        cutoff = (
            datetime.now(pytz.utc)
            - timedelta(hours=hours)
            if hours
            else None
        )

        def check(message):

            if user and message.author != user:
                return False

            if cutoff and message.created_at < cutoff:
                return False

            return True

        try:

            deleted = await interaction.channel.purge(
                limit=min(amount, 300),
                check=check
            )

            await interaction.followup.send(
                f"{len(deleted)}件 削除したで。",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "メッセージを削除する権限が"
                "茜にないみたいや。",
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


async def setup(bot):

    bot.tree.add_command(
        AdminCommands(bot)
    )
