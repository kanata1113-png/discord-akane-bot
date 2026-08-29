import discord


class EventView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    async def _update(
        self,
        interaction: discord.Interaction,
        status: str
    ):

        if not interaction.message.embeds:
            await interaction.response.send_message(
                "イベント情報が見つからへんかったで。",
                ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]

        new_fields = []

        target = f"【{status}】"

        for field in embed.fields:

            values = [
                line
                for line in field.value.split("\n")
                if (
                    interaction.user.mention not in line
                    and "なし" not in line
                )
            ]

            if field.name == target:

                values.append(
                    f"• {interaction.user.mention}"
                )

            new_fields.append(
                (
                    field.name,
                    "\n".join(values) or "なし"
                )
            )

        new_embed = discord.Embed(
            title=embed.title,
            description=embed.description,
            color=embed.color
        )

        if embed.footer.text:

            new_embed.set_footer(
                text=embed.footer.text
            )

        new_embed.timestamp = embed.timestamp

        for name, value in new_fields:

            new_embed.add_field(
                name=name,
                value=value
            )

        await interaction.response.edit_message(
            embed=new_embed,
            view=self
        )

    @discord.ui.button(
        label="参加",
        style=discord.ButtonStyle.success,
        custom_id="ev_join"
    )
    async def join(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self._update(
            interaction,
            "参加"
        )

    @discord.ui.button(
        label="不参加",
        style=discord.ButtonStyle.danger,
        custom_id="ev_leave"
    )
    async def leave(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self._update(
            interaction,
            "不参加"
        )
