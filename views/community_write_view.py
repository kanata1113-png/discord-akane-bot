from __future__ import annotations

import re
from datetime import datetime

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


def _normalize_date(value: str) -> str | None:
    text = value.strip().replace("-", "/").replace(".", "/")
    match = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        checked = datetime(year, month, day)
    except ValueError:
        return None
    return checked.strftime("%Y/%m/%d")


def _normalize_time(value: str) -> str | None:
    text = value.strip().replace("：", ":")
    if re.fullmatch(r"\d{3,4}", text):
        text = text.zfill(4)
        text = f"{text[:2]}:{text[2:]}"
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _normalize_optional_end(value: str, *, start_date: str) -> str | None | bool:
    """Return normalized datetime, None for blank, or False for invalid input."""

    text = value.strip()
    if not text:
        return None

    # Friendly same-day shorthand: "22:00" or "2200".
    time_only = _normalize_time(text)
    if time_only:
        return f"{start_date} {time_only}"

    # Full datetime accepts common separators and any amount of whitespace.
    normalized = text.replace("-", "/").replace(".", "/").replace("　", " ")
    match = re.fullmatch(r"(\d{4}/\d{1,2}/\d{1,2})\s+(\d{1,2}[:：]\d{2}|\d{3,4})", normalized)
    if not match:
        return False
    date_part = _normalize_date(match.group(1))
    time_part = _normalize_time(match.group(2))
    if not date_part or not time_part:
        return False
    return f"{date_part} {time_part}"


class ExternalEventModal(discord.ui.Modal, title="イベント作成：その他 / 外部"):
    event_name = discord.ui.TextInput(label="イベント名", placeholder="例: 読書会", min_length=1, max_length=100)
    start_date = discord.ui.TextInput(label="開始日（日本時間）", placeholder="例: 2026/09/22", min_length=8, max_length=10)
    start_time = discord.ui.TextInput(label="開始時刻（日本時間）", placeholder="例: 18:00", min_length=4, max_length=5)
    end = discord.ui.TextInput(
        label="終了日時（日本時間）",
        placeholder="同日なら 22:00 / 別日なら 2026/09/23 01:00",
        min_length=4,
        max_length=16,
    )
    location = discord.ui.TextInput(label="開催場所・URL", placeholder="例: 東京 / https://...", min_length=1, max_length=100)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = str(self.event_name.value).strip()
        start_date = _normalize_date(str(self.start_date.value))
        start_time = _normalize_time(str(self.start_time.value))
        if not start_date:
            await interaction.response.send_message("📅 開始日は `2026/09/22` のように入力してな。", ephemeral=True)
            return
        if not start_time:
            await interaction.response.send_message("🕐 開始時刻は `18:00` のように入力してな。", ephemeral=True)
            return

        start = f"{start_date} {start_time}"
        end = _normalize_optional_end(str(self.end.value), start_date=start_date)
        if end is False:
            await interaction.response.send_message(
                "🕐 終了は同日なら `22:00`、別日なら `2026/09/23 01:00` のように入力してな。",
                ephemeral=True,
            )
            return

        location = str(self.location.value).strip()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=str(end),
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
            "この内容でDiscord公式イベントを作る？"
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
    event_name = discord.ui.TextInput(label="イベント名", placeholder="例: 読書会", min_length=1, max_length=100)
    start_date = discord.ui.TextInput(label="開始日（日本時間）", placeholder="例: 2026/09/22", min_length=8, max_length=10)
    start_time = discord.ui.TextInput(label="開始時刻（日本時間）", placeholder="例: 18:00", min_length=4, max_length=5)
    end = discord.ui.TextInput(
        label="終了（任意・日本時間）",
        placeholder="同日なら 22:00 / 別日なら 2026/09/23 01:00",
        required=False,
        max_length=16,
    )
    description = discord.ui.TextInput(label="説明（任意）", style=discord.TextStyle.paragraph, required=False, max_length=1000)

    def __init__(self, *, requester_id: int, event_type: str, channel_id: int | None = None) -> None:
        title = "イベント作成：ボイス" if event_type == "voice" else "イベント作成：ステージ"
        super().__init__(title=title)
        self.requester_id = requester_id
        self.event_type = event_type
        self.channel_id = channel_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.channel_id is None:
            await interaction.response.send_message(
                "🔊 開催する部屋を先に選んでな。チャンネルIDを覚える必要はないで。",
                ephemeral=True,
            )
            return

        name = str(self.event_name.value).strip()
        start_date = _normalize_date(str(self.start_date.value))
        start_time = _normalize_time(str(self.start_time.value))
        if not start_date:
            await interaction.response.send_message("📅 開始日は `2026/09/22` のように入力してな。", ephemeral=True)
            return
        if not start_time:
            await interaction.response.send_message("🕐 開始時刻は `18:00` のように入力してな。", ephemeral=True)
            return

        start = f"{start_date} {start_time}"
        end = _normalize_optional_end(str(self.end.value), start_date=start_date)
        if end is False:
            await interaction.response.send_message(
                "🕐 終了は同日なら `22:00`、別日なら `2026/09/23 01:00` のように入力してな。",
                ephemeral=True,
            )
            return

        description = str(self.description.value).strip() or None

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_event(
                confirm_interaction,
                name=name,
                start=start,
                end=str(end) if end else None,
                event_type=self.event_type,
                location=None,
                event_channel_id=self.channel_id,
                description=description,
            )

        kind = "🔊 ボイス" if self.event_type == "voice" else "🎙️ ステージ"
        preview = (
            f"📅 **{name}**\n"
            f"開始: `{start}`\n"
            + (f"終了: `{end}`\n" if end else "")
            + f"形式: **{kind}** / <#{self.channel_id}>\n"
            + (f"説明: {description}\n" if description else "")
            + "\nこの内容でDiscord公式イベントを作る？"
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
        channel_type = discord.ChannelType.voice if event_type == "voice" else discord.ChannelType.stage_voice
        placeholder = "🔊 開催するボイスチャンネルを選んでな" if event_type == "voice" else "🎙️ 開催するステージを選んでな"
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            channel_types=[channel_type],
            custom_id=f"event_channel:{event_type}",
        )
        self.requester_id = requester_id
        self.event_type = event_type

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        channel_id = int(selected.id)
        await interaction.message.edit(
            content=f"✅ 開催場所は <#{channel_id}> やな。次にイベント内容を入力してな ✍️",
            view=None,
        )
        await interaction.response.send_modal(
            ChannelEventModal(
                requester_id=self.requester_id,
                event_type=self.event_type,
                channel_id=channel_id,
            )
        )


class EventChannelSelectView(RequesterOnlyView):
    def __init__(self, *, requester_id: int, event_type: str) -> None:
        super().__init__(requester_id=requester_id)
        self.add_item(EventChannelSelect(requester_id=requester_id, event_type=event_type))
        cancel = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary, custom_id="event_channel:cancel")

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(content="👌 キャンセルしたで。イベントは作ってへんで。", view=self)

        cancel.callback = cancel_callback
        self.add_item(cancel)


class EventTypeChoiceView(RequesterOnlyView):
    """Discord Scheduled Event wizard ordered by the server's common use."""

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
                        content="🌐 その他 / 外部イベントやな。日付と時刻は別々に入力できるで ✍️",
                        view=None,
                    )
                    await interaction.response.send_modal(ExternalEventModal(requester_id=self.requester_id))
                    return

                label_text = "🔊 ボイス" if selected == "voice" else "🎙️ ステージ"
                await interaction.response.edit_message(
                    content=f"{label_text} イベントやな。まず開催する部屋を選んでな👇\nIDを入力する必要はないで。",
                    view=EventChannelSelectView(requester_id=self.requester_id, event_type=selected),
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
                content="👌 キャンセルしたで。イベントは作ってへんで。",
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
            f"📊 **{question}**\n{preview}\nこの内容で投票を作る？",
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
            await self.begin(interaction)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="👌 キャンセルしたで。作成はしてへんで。",
                view=self,
            )

        select.callback = select_callback
        cancel.callback = cancel_callback
        self.add_item(select)
        self.add_item(cancel)

    async def begin(self, interaction: discord.Interaction) -> None:
        self.disable_all()
        self.stop()
        if self.capability_id == "event_create":
            await interaction.response.edit_message(
                content=(
                    "📅 イベントを作るんやな！開催形式を選んでな👇\n"
                    "一番よく使う **ボイス** を先頭にしてあるで。"
                ),
                view=EventTypeChoiceView(requester_id=self.requester_id),
            )
            return

        await interaction.message.edit(
            content=(
                f"✨ **{self.capability_name}** の操作を始めるで。\n"
                "内容を入力したあと、最後にちゃんと確認するから安心してな👌"
            ),
            view=None,
        )
        if self.capability_id == "poll_create":
            await interaction.response.send_modal(PollCreateModal(requester_id=self.requester_id))
            return
        await interaction.response.send_message(
            "この機能はまだ確認フロー対象外やで。",
            ephemeral=True,
        )
