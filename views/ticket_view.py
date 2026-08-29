import asyncio
import logging
import discord


logger = logging.getLogger("AkaneBot")


class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="問い合わせ",
        style=discord.ButtonStyle.primary,
        emoji="📩",
        custom_id="tk_open"
    )
    async def create(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能はサーバー内専用やで。",
                ephemeral=True
            )

            return

        try:

            overwrites = {
                interaction.guild.default_role:
                    discord.PermissionOverwrite(
                        read_messages=False
                    ),

                interaction.user:
                    discord.PermissionOverwrite(
                        read_messages=True
                    ),

                interaction.guild.me:
                    discord.PermissionOverwrite(
                        read_messages=True
                    ),
            }

            channel = await interaction.guild.create_text_channel(
                f"ticket-{interaction.user.name}",
                overwrites=overwrites
            )

            await interaction.response.send_message(
                f"個室を作ったで！: {channel.mention}",
                ephemeral=True
            )

            await channel.send(
                f"{interaction.user.mention} "
                "ここで要件を聞くで。",
                view=TicketCloseView()
            )

        except discord.Forbidden:

            logger.warning(
                "Ticket creation permission denied."
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "チケットを作る権限が茜にないみたいや。",
                    ephemeral=True
                )

        except Exception as e:

            logger.exception(
                f"Ticket creation failed: {e}"
            )

            if not interaction.response.is_done():

                await interaction.response.send_message(
                    "チケット作成中にエラーが起きたで。",
                    ephemeral=True
                )


class TicketCloseView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="解決・閉じる",
        style=discord.ButtonStyle.danger,
        custom_id="tk_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:

            await interaction.response.send_message(
                "ほな閉じるで〜"
            )

            await asyncio.sleep(3)

            await interaction.channel.delete()

        except discord.Forbidden:

            logger.warning(
                "Ticket channel delete permission denied."
            )

        except Exception as e:

            logger.exception(
                f"Ticket close failed: {e}"
            )
