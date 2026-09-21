from __future__ import annotations

import discord

from views.write_capability_view import ConfirmActionView, RequesterOnlyView


async def _general_cog(interaction: discord.Interaction):
    cog = interaction.client.get_cog("GeneralCog")
    if cog is None:
        raise RuntimeError("GeneralCog unavailable")
    return cog


async def _invoke_event(
    interaction: discord.Interaction,
    title: str,
    date: str,
    time: str,
) -> None:
    cog = await _general_cog(interaction)
    await cog.event.callback(cog, interaction, title, date, time)


async def _invoke_poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: str,
    option3: str | None,
    option4: str | None,
) -> None:
    cog = await _general_cog(interaction)
    await cog.poll.callback(
        cog,
        interaction,
        question,
        option1,
        option2,
        option3,
        option4,
    )


class EventCreateModal(discord.ui.Modal, title="イベント作成"):
    event_title = discord.ui.TextInput(label="イベント名", min_length=1, max_length=100)
    date = discord.ui.TextInput(label="日付", placeholder="YYYY/MM/DD", min_length=10, max_length=10)
    time = discord.ui.TextInput(label="時刻", placeholder="HH:MM", min_length=5, max_length=5)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        title = str(self.event_title.value).strip()
        date = str(self.date.value).strip()
        time = str(self.time.value).strip()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(confirm_interaction, title, date, time)

        await interaction.response.send_message(
            f"**{title}** を `{date} {time}` に作成する？\n確定するまで作成はされへんで。",
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="イベント作成を確定",
            ),
            ephemeral=True,
        )


class PollCreateModal(discord.ui.Modal, title="投票作成"):
    question = discord.ui.TextInput(label="質問", min_length=1, max_length=200)
    option1 = discord.ui.TextInput(label="選択肢1", min_length=1, max_length=100)
    option2 = discord.ui.TextInput(label="選択肢2", min_length=1, max_length=100)
    option3 = discord.ui.TextInput(label="選択肢3（任意）", required=False, max_length=100)
    option4 = discord.ui.TextInput(label="選択肢4（任意）", required=False, max_length=100)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        question = str(self.question.value).strip()
        option1 = str(self.option1.value).strip()
        option2 = str(self.option2.value).strip()
        option3 = str(self.option3.value).strip() or None
        option4 = str(self.option4.value).strip() or None

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_poll(
                confirm_interaction,
                question,
                option1,
                option2,
                option3,
                option4,
            )

        preview = " / ".join(
            item for item in (option1, option2, option3, option4) if item
        )
        await interaction.response.send_message(
            f"**{question}**\n{preview}\nこの内容で投票を作る？",
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="投票作成を確定",
            ),
            ephemeral=True,
        )


class CommunityWriteEntryView(RequesterOnlyView):
    def __init__(self, *, requester_id: int, capability_id: str, capability_name: str) -> None:
        super().__init__(requester_id=requester_id)
        self.capability_id = capability_id
        self.capability_name = capability_name

        select = discord.ui.Button(
            label=capability_name[:80],
            style=discord.ButtonStyle.secondary,
            custom_id=f"community_write:{capability_id}",
        )
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="community_write:cancel",
        )

        async def select_callback(interaction: discord.Interaction) -> None:
            self.disable_all()
            self.stop()
            await interaction.message.edit(
                content=(
                    f"選択: **{self.capability_name}**\n"
                    "入力内容を確認したあと、最終確認するで。"
                ),
                view=self,
            )
            if self.capability_id == "event_create":
                await interaction.response.send_modal(
                    EventCreateModal(requester_id=self.requester_id)
                )
                return
            if self.capability_id == "poll_create":
                await interaction.response.send_modal(
                    PollCreateModal(requester_id=self.requester_id)
                )
                return
            await interaction.response.send_message(
                "この機能はまだ確認フロー対象外やで。",
                ephemeral=True,
            )

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。作成はしてへんで。",
                view=self,
            )

        select.callback = select_callback
        cancel.callback = cancel_callback
        self.add_item(select)
        self.add_item(cancel)
