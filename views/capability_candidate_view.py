from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import discord

from services.capability_discovery import DiscoveryCandidate
from services.discovery_direct_execution import execute_selected_read_only


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    capability_id: str
    slash_command: str | None


class CapabilityCandidateView(discord.ui.View):
    """Explicit-selection discovery panel.

    Discovery itself never executes a capability. Direct execution is attempted
    only after the requesting user presses a candidate button, through the
    narrow read-only execution policy. Unsupported candidates remain
    selection-only and fall back to the existing slash-command guidance.
    Cancellation never invokes execution.
    """

    def __init__(
        self,
        candidates: Sequence[DiscoveryCandidate],
        *,
        requester_id: int,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.selection: CandidateSelection | None = None
        self.cancelled = False

        for candidate in tuple(candidates)[:4]:
            button = discord.ui.Button(
                label=candidate.name[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"cap_discovery:{candidate.capability_id}",
            )

            async def callback(
                interaction: discord.Interaction,
                *,
                selected=candidate,
            ) -> None:
                await self._select(interaction, selected)

            button.callback = callback
            self.add_item(button)

        cancel_button = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="cap_discovery:cancel",
        )

        async def cancel_callback(
            interaction: discord.Interaction,
        ) -> None:
            await self._cancel(interaction)

        cancel_button.callback = cancel_callback
        self.add_item(cancel_button)

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.requester_id:
            return True

        await interaction.response.send_message(
            "この候補はリクエストした本人だけ選べるで。",
            ephemeral=True,
        )
        return False

    async def _select(
        self,
        interaction: discord.Interaction,
        candidate: DiscoveryCandidate,
    ) -> None:
        self.selection = CandidateSelection(
            candidate.capability_id,
            candidate.slash_command,
        )

        for item in self.children:
            item.disabled = True

        command = candidate.slash_command or candidate.name

        try:
            executed = await execute_selected_read_only(
                interaction,
                candidate,
            )
        except Exception:
            if interaction.response.is_done():
                if interaction.message is not None:
                    await interaction.message.edit(
                        content=(
                            f"選択: **{candidate.name}**\n"
                            "実行中にエラーが起きたため、ここで終了したで。"
                        ),
                        view=self,
                    )
            else:
                await interaction.response.edit_message(
                    content=(
                        f"選択: **{candidate.name}**\n"
                        "実行中にエラーが起きたため、ここで終了したで。"
                    ),
                    view=self,
                )
            self.stop()
            return

        if executed:
            if interaction.message is not None:
                await interaction.message.edit(
                    content=(
                        f"実行済み: **{candidate.name}**\n"
                        "この候補の処理はここで終了したで。"
                    ),
                    view=self,
                )
        else:
            await interaction.response.edit_message(
                content=(
                    f"選択: **{candidate.name}**\n"
                    f"使うコマンドは `{command}` やで。"
                    "\n※ この候補は直接実行せず、コマンド案内で終了するで。"
                ),
                view=self,
            )

        self.stop()

    async def _cancel(
        self,
        interaction: discord.Interaction,
    ) -> None:
        self.cancelled = True
        self.selection = None

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=(
                "キャンセル済みやで。\n"
                "このメッセージの処理はここで終了したで。"
            ),
            view=self,
        )
        self.stop()


def candidate_panel_text(
    candidates: Sequence[DiscoveryCandidate],
) -> str:
    count = min(len(tuple(candidates)), 4)
    return (
        "もしかして、次の機能を探してる？\n"
        f"候補は{count}件や。使いたいものを選んでな。"
        "\n※ 対応している読み取り機能は選択後にそのまま実行するで。"
        "未対応の候補は既存コマンドを案内するで。"
    )
