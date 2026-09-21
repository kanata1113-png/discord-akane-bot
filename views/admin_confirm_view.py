from __future__ import annotations

from typing import Awaitable, Callable

import discord


AdminCallback = Callable[[discord.Interaction], Awaitable[None]]


class AdminConfirmView(discord.ui.View):
    """Requester-only confirmation that rechecks administrator permission."""

    def __init__(
        self,
        *,
        requester_id: int,
        on_confirm: AdminCallback,
        confirm_label: str,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self._on_confirm = on_confirm
        self.confirmed = False
        self.cancelled = False

        confirm = discord.ui.Button(
            label=confirm_label,
            style=discord.ButtonStyle.danger,
            custom_id="admin_confirm:confirm",
        )
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="admin_confirm:cancel",
        )

        async def confirm_callback(interaction: discord.Interaction) -> None:
            if not await self.interaction_check(interaction):
                return
            permissions = getattr(interaction.user, "guild_permissions", None)
            if interaction.guild is None or permissions is None or not permissions.administrator:
                await interaction.response.send_message(
                    "⛔ 管理者権限を確認できへんかったから実行せえへんで。",
                    ephemeral=True,
                )
                return
            self.confirmed = True
            self.disable_all()
            self.stop()
            await self._on_confirm(interaction)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            if not await self.interaction_check(interaction):
                return
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセル済みやで。管理操作は実行してへんで。",
                view=self,
            )

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "この管理操作はリクエストした本人だけ確定できるで。",
            ephemeral=True,
        )
        return False

    def disable_all(self) -> None:
        for item in self.children:
            item.disabled = True
