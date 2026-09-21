from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import discord

from services.capability_discovery import DiscoveryCandidate


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    capability_id: str
    slash_command: str | None


class CapabilityCandidateView(discord.ui.View):
    """Selection-only discovery panel.

    Buttons record which existing slash capability the requesting user selected.
    This view deliberately has no dispatcher or handler reference, so selection
    cannot execute a capability.
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
        await interaction.response.edit_message(
            content=(
                f"選択: **{candidate.name}**\n"
                f"使うコマンドは `{command}` やで。"
                "\n※ まだ自動実行はしてへんで。"
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
        "\n※ 選んでも、この段階ではコマンドは自動実行されへんで。"
    )
