from __future__ import annotations

from datetime import datetime, timedelta

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


def _event_datetime_strings(
    start_date: str,
    start_time: str,
    end_time: str | None,
) -> tuple[str, str | None]:
    """Build legacy event datetime strings from mobile-friendly inputs.

    The end time is treated as the same date; if it is earlier than/equal to the
    start time we interpret it as crossing midnight into the next day.
    """

    try:
        start_dt = datetime.strptime(
            f"{start_date.strip()} {start_time.strip()}",
            "%Y/%m/%d %H:%M",
        )
    except ValueError as exc:
        raise ValueError("invalid_start_fields") from exc

    start = start_dt.strftime("%Y/%m/%d %H:%M")
    if not end_time or not end_time.strip():
        return start, None

    try:
        end_clock = datetime.strptime(end_time.strip(), "%H:%M").time()
    except ValueError as exc:
        raise ValueError("invalid_end_time") from exc

    end_dt = datetime.combine(start_dt.date(), end_clock)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start, end_dt.strftime("%Y/%m/%d %H:%M")


async def _send_datetime_error(interaction: discord.Interaction, error: ValueError) -> None:
    if str(error) == "invalid_end_time":
        text = "🕐 終了時刻は `22:00` みたいに **HH:MM** で入力してな。"
    else:
        text = (
            "📅 日付は `2026/09/22`、開始時刻は `18:00` みたいに分けて入力してな。\n"
            "半角スペースを自分で入れる必要はないで👌"
        )
    await interaction.response.send_message(text, ephemeral=True)


class ExternalEventModal(discord.ui.Modal, title="イベント作成：その他 / 外部"):
    event_name = discord.ui.TextInput(
        label="イベント名",
        placeholder="例：読書会",
        min_length=1,
        max_length=100,
    )
    start_date = discord.ui.TextInput(
        label="開始日（日本時間）",
        placeholder="例：2026/09/22",
        min_length=10,
        max_length=10,
    )
    start_time = discord.ui.TextInput(
        label="開始時刻（日本時間）",
        placeholder="例：18:00",
        min_length=5,
        max_length=5,
    )
    end_time = discord.ui.TextInput(
        label="終了時刻（必須）",
        placeholder="例：22:00（開始より早ければ翌日扱い）",
        min_length=5,
        max_length=5,
    )
    location = discord.ui.TextInput(
        label="開催場所・URL",
        placeholder="例：https://example.com / 会議室A",
        min_length=1,
        max_length=100,
    )

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            start, end = _event_datetime_strings(
                str(self.start_date.value),
                str(self.start_time.value),
                str(self.end_time.value),
            )
        except ValueError as exc:
            await _send_datetime_error(interaction, exc)
            return

        name = str(self.event_name.value).strip()
        location = str(self.location.value).strip()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=end,
                event_type="external",
                location=location,
                event_channel_id=None,
                description=None,
            )

        preview = (
            f"🌐 **{name}**\n"
            f"📅 開始: `{start}`\n"
            f"🕐 終了: `{end}`\n"
            f"📍 場所: **{location}**\n\n"
            "この内容でDiscord公式イベントを作成する？"
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
    event_name = discord.ui.TextInput(
        label="イベント名",
        placeholder="例：読書会",
        min_length=1,
        max_length=100,
    )
    start_date = discord.ui.TextInput(
        label="開始日（日本時間）",
        placeholder="例：2026/09/22",
        min_length=10,
        max_length=10,
    )
    start_time = discord.ui.TextInput(
        label="開始時刻（日本時間）",
        placeholder="例：18:00",
        min_length=5,
        max_length=5,
    )
    end_time = discord.ui.TextInput(
        label="終了時刻（任意）",
        placeholder="例：22:00（空欄OK）",
        required=False,
        max_length=5,
    )
    description = discord.ui.TextInput(
        label="説明（任意）",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )

    def __init__(
        self,
        *,
        requester_id: int,
        event_type: str,
        event_channel_id: int,
    ) -> None:
        title = "イベント作成：ボイス" if event_type == "voice" else "イベント作成：ステージ"
        super().__init__(title=title)
        self.requester_id = requester_id
        self.event_type = event_type
        self.event_channel_id = event_channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            start, end = _event_datetime_strings(
                str(self.start_date.value),
                str(self.start_time.value),
                str(self.end_time.value) or None,
            )
        except ValueError as exc:
            await _send_datetime_error(interaction, exc)
            return

        name = str(self.event_name.value).strip()
        description = str(self.description.value).strip() or None

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=end,
                event_type=self.event_type,
                location=None,
                event_channel_id=self.event_channel_id,
                description=description,
            )

        kind = "🔊 ボイス" if self.event_type == "voice" else "🎙️ ステージ"
        preview = (
            f"📅 **{name}**\n"
            f"開始: `{start}`\n"
            + (f"終了: `{end}`\n" if end else "")
            + f"形式: **{kind}** / <#{self.event_channel_id}>\n"
            + (f"説明: {description}\n" if description else "")
            + "\nこの内容でDiscord公式イベントを作成する？"
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


class EventChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, *, requester_id: int, event_type: str) -> None:
        self.requester_id = requester_id
        self.event_type = event_type
        channel_type = (
            discord.ChannelType.voice
            if event_type == "voice"
            else discord.ChannelType.stage_voice
        )
        label = "ボイス" if event_type == "voice" else "ステージ"
        super().__init__(
            placeholder=f"開催する{label}チャンネルを選んでな",
            min_values=1,
            max_values=1,
            channel_types=[channel_type],
            custom_id=f"event_channel:{event_type}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "この操作はリクエストした本人だけ使えるで。",
                ephemeral=True,
            )
            return
        selected = self.values[0]
        await interaction.response.send_modal(
            ChannelEventModal(
                requester_id=self.requester_id,
                event_type=self.event_type,
                event_channel_id=int(selected.id),
            )
        )


class EventChannelSelectView(RequesterOnlyView):
    def __init__(self, *, requester_id: int, event_type: str) -> None:
        super().__init__(requester_id=requester_id)
        self.event_type = event_type
        self.add_item(
            EventChannelSelect(
                requester_id=requester_id,
                event_type=event_type,
            )
        )
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
                content="キャンセルしたで👌 イベントは作成してへんで。",
                view=self,
            )

        cancel.callback = cancel_callback
        self.add_item(cancel)


class EventTypeChoiceView(RequesterOnlyView):
    """Mirrors Discord Scheduled Event types in expected usage order."""

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
                if selected == "external":
                    await interaction.message.edit(
                        content=(
                            "🌐 その他 / 外部イベントやな。\n"
                            "日付と時刻は分けて入力できるようにしたで👌"
                        ),
                        view=self,
                    )
                    await interaction.response.send_modal(
                        ExternalEventModal(requester_id=self.requester_id)
                    )
                    return

                kind = "ボイス" if selected == "voice" else "ステージ"
                await interaction.response.edit_message(
                    content=(
                        f"{('🔊' if selected == 'voice' else '🎙️')} **{kind}イベント**やな！\n"
                        "開催する部屋を下の一覧から選んでな👇 IDを覚える必要はないで。"
                    ),
                    view=EventChannelSelectView(
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
                content="キャンセルしたで👌 イベントは作成してへんで。",
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
            f"📊 **{question}**\n{preview}\n\nこの内容で投票を作る？",
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
                    content=(
                        "📅 開催形式を選んでな👇\n"
                        "よく使う順に **ボイス → ステージ → その他 / 外部** で並べてるで。"
                    ),
                    view=EventTypeChoiceView(requester_id=self.requester_id),
                )
                return

            await interaction.message.edit(
                content=(
                    f"✨ **{self.capability_name}** やな。\n"
                    "入力内容を確認したあと、最終確認するで👌"
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
                content="キャンセルしたで👌 作成はしてへんで。",
                view=self,
            )

        select.callback = select_callback
        cancel.callback = cancel_callback
        self.add_item(select)
        self.add_item(cancel)
