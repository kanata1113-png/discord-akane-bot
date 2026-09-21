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
    *,
    name: str,
    start: str,
    end: str | None,
    event_type: str,
    location: str | None,
    event_channel_id: int | None,
    description: str | None,
) -> None:
    cog = await _general_cog(interaction)
    await cog.event.callback(
        cog,
        interaction,
        name,
        start,
        event_type,
        end,
        location,
        discord.Object(id=event_channel_id) if event_channel_id else None,
        description,
    )


async def _invoke_poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: str,
    option3: str | None,
    option4: str | None,
) -> None:
    cog = await _general_cog(interaction)
    await cog.poll.callback(cog, interaction, question, option1, option2, option3, option4)


def _resolve_channel_id(guild: discord.Guild | None, value: str, *, event_type: str) -> int | None:
    if guild is None:
        return None
    text = value.strip().replace("<#", "").replace(">", "")
    if text.isdigit():
        channel = guild.get_channel(int(text))
        if channel is not None:
            return channel.id
    expected = discord.VoiceChannel if event_type == "voice" else discord.StageChannel
    for channel in guild.channels:
        if isinstance(channel, expected) and channel.name == value.strip().lstrip("#"):
            return channel.id
    return None


class ExternalEventModal(discord.ui.Modal, title="イベント作成：その他/外部"):
    event_name = discord.ui.TextInput(label="イベント名", min_length=1, max_length=100)
    start = discord.ui.TextInput(label="開始（日本時間）", placeholder="YYYY/MM/DD HH:MM", min_length=16, max_length=16)
    end = discord.ui.TextInput(label="終了（日本時間）", placeholder="YYYY/MM/DD HH:MM", min_length=16, max_length=16)
    location = discord.ui.TextInput(label="開催場所・URL", min_length=1, max_length=100)
    description = discord.ui.TextInput(label="説明（任意）", style=discord.TextStyle.paragraph, required=False, max_length=1000)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = str(self.event_name.value).strip()
        start = str(self.start.value).strip()
        end = str(self.end.value).strip()
        location = str(self.location.value).strip()
        description = str(self.description.value).strip() or None

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=end,
                event_type="external",
                location=location,
                event_channel_id=None,
                description=description,
            )

        preview = (
            f"📅 **{name}**\n"
            f"開始: `{start}`\n終了: `{end}`\n"
            f"場所: **{location}**\n"
            + (f"説明: {description}\n" if description else "")
            + "Discord公式スケジュールイベントとして作成する？"
        )
        await interaction.response.send_message(
            preview,
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="公式イベントを作成",
            ),
            ephemeral=True,
        )


class ChannelEventModal(discord.ui.Modal):
    event_name = discord.ui.TextInput(label="イベント名", min_length=1, max_length=100)
    start_date = discord.ui.TextInput(label="開始日（日本時間）", placeholder="2026/09/22", min_length=10, max_length=10)
    start_time = discord.ui.TextInput(label="開始時刻（日本時間）", placeholder="18:00", min_length=5, max_length=5)
    end_date = discord.ui.TextInput(label="終了日（任意・日本時間）", placeholder="2026/09/22", required=False, max_length=10)
    end_time = discord.ui.TextInput(label="終了時刻（任意・日本時間）", placeholder="22:00", required=False, max_length=5)

    def __init__(self, *, requester_id: int, event_type: str, channel_id: int) -> None:
        title = "イベント作成：ボイス" if event_type == "voice" else "イベント作成：ステージ"
        super().__init__(title=title)
        self.requester_id = requester_id
        self.event_type = event_type
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = str(self.event_name.value).strip()
        start_date = str(self.start_date.value).strip()
        start_time = str(self.start_time.value).strip()
        end_date = str(self.end_date.value).strip()
        end_time = str(self.end_time.value).strip()
        start = f"{start_date} {start_time}"
        if bool(end_date) != bool(end_time):
            await interaction.response.send_message(
                "📅 終了日時を入れるときは、終了日と終了時刻を両方入れてな。",
                ephemeral=True,
            )
            return
        end = f"{end_date} {end_time}" if end_date and end_time else None

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=end,
                event_type=self.event_type,
                location=None,
                event_channel_id=self.channel_id,
                description=None,
            )

        kind = "🔊 ボイス" if self.event_type == "voice" else "🎙️ ステージ"
        preview = (
            f"📅 **{name}**\n"
            f"開始: `{start}`\n"
            + (f"終了: `{end}`\n" if end else "")
            + f"形式: **{kind}** / <#{self.channel_id}>\n"
            + "この内容でDiscord公式イベントを作る？"
        )
        await interaction.response.send_message(
            preview,
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="イベントを作成",
            ),
            ephemeral=True,
        )


class EventChannelChoiceView(RequesterOnlyView):
    def __init__(self, *, requester_id: int, event_type: str) -> None:
        super().__init__(requester_id=requester_id)
        self.event_type = event_type
        channel_type = (
            discord.ChannelType.voice
            if event_type == "voice"
            else discord.ChannelType.stage_voice
        )
        select = discord.ui.ChannelSelect(
            placeholder="開催する部屋を選んでな",
            min_values=1,
            max_values=1,
            channel_types=[channel_type],
            custom_id=f"event_channel:{event_type}",
        )

        async def select_callback(interaction: discord.Interaction) -> None:
            selected = select.values[0]
            channel_id = int(selected.id)
            self.disable_all()
            self.stop()
            await interaction.response.send_modal(
                ChannelEventModal(
                    requester_id=self.requester_id,
                    event_type=self.event_type,
                    channel_id=channel_id,
                )
            )

        select.callback = select_callback
        self.add_item(select)

        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id=f"event_channel:{event_type}:cancel",
        )

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセルしたで。イベントは作成してへんで。",
                view=self,
            )

        cancel.callback = cancel_callback
        self.add_item(cancel)


class EventTypeChoiceView(RequesterOnlyView):
    """Mirrors Discord's three Scheduled Event location choices."""

    def __init__(self, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        choices = (
            ("🔊 ボイス", "voice", discord.ButtonStyle.primary),
            ("🎙️ ステージ", "stage", discord.ButtonStyle.secondary),
            ("🌐 その他 / 外部", "external", discord.ButtonStyle.secondary),
        )
        for label, event_type, style in choices:
            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"event_type:{event_type}",
            )

            async def callback(interaction: discord.Interaction, *, selected=event_type) -> None:
                self.disable_all()
                self.stop()
                await interaction.message.edit(
                    content=f"開催形式: **{selected}**\nDiscord公式の項目を入力してな。",
                    view=self,
                )
                if selected == "external":
                    await interaction.response.send_modal(ExternalEventModal(requester_id=self.requester_id))
                else:
                    await interaction.response.edit_message(
                        content="🏠 開催する部屋を選んでな👇",
                        view=EventChannelChoiceView(
                            requester_id=self.requester_id,
                            event_type=selected,
                        ),
                    )

            button.callback = callback
            self.add_item(button)

        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="event_type:cancel",
        )

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。イベントは作成してへんで。",
                view=self,
            )

        cancel.callback = cancel_callback
        self.add_item(cancel)


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
            await _invoke_poll(confirm_interaction, question, option1, option2, option3, option4)

        preview = " / ".join(item for item in (option1, option2, option3, option4) if item)
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
            if self.capability_id == "event_create":
                await interaction.response.edit_message(
                    content="Discord公式イベントの開催形式を選んでな。",
                    view=EventTypeChoiceView(requester_id=self.requester_id),
                )
                return

            await interaction.message.edit(
                content=(
                    f"選択: **{self.capability_name}**\n"
                    "入力内容を確認したあと、最終確認するで。"
                ),
                view=self,
            )
            if self.capability_id == "poll_create":
                await interaction.response.send_modal(PollCreateModal(requester_id=self.requester_id))
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
