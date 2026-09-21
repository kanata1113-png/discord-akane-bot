from __future__ import annotations

from typing import Awaitable, Callable

import discord


ConfirmCallback = Callable[[discord.Interaction], Awaitable[None]]


async def _general_cog(interaction: discord.Interaction):
    cog = interaction.client.get_cog("GeneralCog")
    if cog is None:
        raise RuntimeError("GeneralCog unavailable")
    return cog


async def _invoke_title_set(interaction: discord.Interaction, title_key: str) -> None:
    cog = await _general_cog(interaction)
    await cog.title_set.callback(cog, interaction, title_key)


async def _invoke_forget(interaction: discord.Interaction, all_channels: bool) -> None:
    cog = await _general_cog(interaction)
    await cog.forget.callback(cog, interaction, all_channels)


async def _invoke_remind(
    interaction: discord.Interaction,
    minutes: int,
    message: str,
) -> None:
    cog = await _general_cog(interaction)
    await cog.remind.callback(cog, interaction, minutes, message)


class RequesterOnlyView(discord.ui.View):
    def __init__(self, *, requester_id: int, timeout: float = 120.0) -> None:
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.cancelled = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "この操作はリクエストした本人だけ使えるで。",
            ephemeral=True,
        )
        return False

    def disable_all(self) -> None:
        for item in self.children:
            item.disabled = True


class ConfirmActionView(RequesterOnlyView):
    def __init__(
        self,
        *,
        requester_id: int,
        on_confirm: ConfirmCallback,
        confirm_label: str = "実行を確定",
    ) -> None:
        super().__init__(requester_id=requester_id)
        self._on_confirm = on_confirm
        self.confirmed = False

        confirm = discord.ui.Button(
            label=confirm_label,
            style=discord.ButtonStyle.danger,
            custom_id="write_confirm:confirm",
        )
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="write_confirm:cancel",
        )

        async def confirm_callback(interaction: discord.Interaction) -> None:
            self.confirmed = True
            self.disable_all()
            self.stop()
            await self._on_confirm(interaction)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。書き込みはしてへんで。",
                view=self,
            )

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)


class TitleSetModal(discord.ui.Modal, title="称号変更"):
    title_key = discord.ui.TextInput(
        label="称号キー",
        placeholder="例: contributor",
        min_length=1,
        max_length=80,
    )

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        key = str(self.title_key.value).strip().lower()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_title_set(confirm_interaction, key)

        await interaction.response.send_message(
            f"称号キー `{key}` に変更する？\n確定するまで変更はされへんで。",
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="称号変更を確定",
            ),
            ephemeral=True,
        )


class RemindModal(discord.ui.Modal, title="リマインダー登録"):
    minutes = discord.ui.TextInput(
        label="何分後？",
        placeholder="1〜10080",
        min_length=1,
        max_length=5,
    )
    reminder_message = discord.ui.TextInput(
        label="知らせる内容",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=500,
    )

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            minutes = int(str(self.minutes.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "分数は数字で入力してな。",
                ephemeral=True,
            )
            return

        if minutes < 1 or minutes > 10080:
            await interaction.response.send_message(
                "分数は1〜10080の範囲で入力してな。",
                ephemeral=True,
            )
            return

        reminder_message = str(self.reminder_message.value).strip()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _invoke_remind(
                confirm_interaction,
                minutes,
                reminder_message,
            )

        await interaction.response.send_message(
            (
                f"**{minutes}分後**に「{reminder_message}」で登録する？\n"
                "確定するまで登録はされへんで。"
            ),
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="登録を確定",
            ),
            ephemeral=True,
        )


class ForgetScopeView(RequesterOnlyView):
    def __init__(self, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)

        current = discord.ui.Button(
            label="このチャンネルのみ",
            style=discord.ButtonStyle.secondary,
            custom_id="write_forget:channel",
        )
        all_channels = discord.ui.Button(
            label="全チャンネル",
            style=discord.ButtonStyle.danger,
            custom_id="write_forget:all",
        )
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="write_forget:cancel",
        )

        async def choose(interaction: discord.Interaction, *, all_: bool) -> None:
            async def execute(confirm_interaction: discord.Interaction) -> None:
                await _invoke_forget(confirm_interaction, all_)

            label = "全チャンネルの会話履歴" if all_ else "このチャンネルの会話履歴"
            await interaction.response.edit_message(
                content=f"**{label}**を削除する？\nこの操作は取り消せへんで。",
                view=ConfirmActionView(
                    requester_id=self.requester_id,
                    on_confirm=execute,
                    confirm_label="削除を確定",
                ),
            )
            self.stop()

        async def current_callback(interaction: discord.Interaction) -> None:
            await choose(interaction, all_=False)

        async def all_callback(interaction: discord.Interaction) -> None:
            await choose(interaction, all_=True)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。履歴は削除してへんで。",
                view=self,
            )

        current.callback = current_callback
        all_channels.callback = all_callback
        cancel.callback = cancel_callback
        self.add_item(current)
        self.add_item(all_channels)
        self.add_item(cancel)


class WriteCapabilityEntryView(RequesterOnlyView):
    """Entry point for the Release D WRITE_CONFIRM pilot.

    Selecting the capability never performs a write. It only opens argument or
    scope collection. Actual execution requires a later explicit confirmation.
    """

    def __init__(
        self,
        *,
        requester_id: int,
        capability_id: str,
        capability_name: str,
    ) -> None:
        super().__init__(requester_id=requester_id)
        self.capability_id = capability_id
        self.capability_name = capability_name

        select = discord.ui.Button(
            label=capability_name[:80],
            style=discord.ButtonStyle.secondary,
            custom_id=f"write_entry:{capability_id}",
        )
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="write_entry:cancel",
        )

        async def select_callback(interaction: discord.Interaction) -> None:
            self.disable_all()
            self.stop()

            if self.capability_id == "memory_forget":
                await interaction.response.edit_message(
                    content="削除する会話履歴の範囲を選んでな。",
                    view=ForgetScopeView(requester_id=self.requester_id),
                )
                return

            await interaction.message.edit(
                content=(
                    f"選択: **{self.capability_name}**\n"
                    "入力内容を確認したあと、もう一度最終確認するで。"
                ),
                view=self,
            )

            if self.capability_id == "title_set":
                await interaction.response.send_modal(
                    TitleSetModal(requester_id=self.requester_id)
                )
                return

            if self.capability_id == "remind":
                await interaction.response.send_modal(
                    RemindModal(requester_id=self.requester_id)
                )
                return

            await interaction.response.send_message(
                "この書き込み機能はまだ確認フロー対象外やで。",
                ephemeral=True,
            )

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。書き込みはしてへんで。",
                view=self,
            )

        select.callback = select_callback
        cancel.callback = cancel_callback
        self.add_item(select)
        self.add_item(cancel)


def write_capability_panel_text(capability_name: str) -> str:
    return (
        f"**{capability_name}** の操作かな？\n"
        "書き込み系の機能やから、選択後に内容確認と最終確認を挟むで。"
    )
