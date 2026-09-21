from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

import discord

from services.capability_discovery import DiscoveryCandidate
from services.discovery_selection_executor import execute_discovery_selection
from views.community_write_view import CommunityWriteEntryView
from views.write_capability_view import (
    WriteCapabilityEntryView,
    write_capability_panel_text,
)


# Frozen Release D contract. Existing D regression tests intentionally assert
# this exact set so later releases cannot silently rewrite historical scope.
WRITE_CONFIRM_DISCOVERY_IDS = frozenset(
    {"title_set", "memory_forget", "remind"}
)

COMMUNITY_WRITE_DISCOVERY_IDS = frozenset({"event_create", "poll_create"})
RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS = frozenset(
    {*WRITE_CONFIRM_DISCOVERY_IDS, *COMMUNITY_WRITE_DISCOVERY_IDS}
)


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    capability_id: str
    slash_command: str | None


SelectionCallback = Callable[
    [discord.Interaction, CandidateSelection],
    Awaitable[bool],
]


class CapabilityCandidateView(discord.ui.View):
    """Discovery panel gated by an explicit requester selection."""

    def __init__(
        self,
        candidates: Sequence[DiscoveryCandidate],
        *,
        requester_id: int,
        timeout: float = 60.0,
        on_select: SelectionCallback | None = execute_discovery_selection,
    ) -> None:
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.selection: CandidateSelection | None = None
        self.cancelled = False
        self._on_select = on_select

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

        async def cancel_callback(interaction: discord.Interaction) -> None:
            await self._cancel(interaction)

        cancel_button.callback = cancel_callback
        self.add_item(cancel_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
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
        self.stop()

        if candidate.capability_id in RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS:
            if candidate.capability_id in COMMUNITY_WRITE_DISCOVERY_IDS:
                view = CommunityWriteEntryView(
                    requester_id=self.requester_id,
                    capability_id=candidate.capability_id,
                    capability_name=candidate.name,
                )
            else:
                view = WriteCapabilityEntryView(
                    requester_id=self.requester_id,
                    capability_id=candidate.capability_id,
                    capability_name=candidate.name,
                )
            await interaction.response.edit_message(
                content=write_capability_panel_text(candidate.name),
                view=view,
            )
            return

        if self._on_select is None:
            command = candidate.slash_command or candidate.name
            await interaction.response.edit_message(
                content=(
                    f"選択: **{candidate.name}**\n"
                    f"使うコマンドは `{command}` やで。"
                    "\n※ まだ自動実行はしてへんで。"
                ),
                view=self,
            )
            return

        executed = await self._on_select(interaction, self.selection)
        if executed:
            content = f"実行済み: **{candidate.name}**"
        else:
            command = candidate.slash_command or candidate.name
            content = (
                f"選択: **{candidate.name}**\n"
                "この機能はこの画面からの直接実行対象外やで。\n"
                f"必要なら `{command}` を使ってな。"
            )

        if interaction.response.is_done():
            await interaction.message.edit(content=content, view=self)
        else:
            await interaction.response.edit_message(content=content, view=self)

    async def _cancel(self, interaction: discord.Interaction) -> None:
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


def candidate_panel_text(candidates: Sequence[DiscoveryCandidate]) -> str:
    count = min(len(tuple(candidates)), 4)
    return (
        "もしかして、次の機能を探してる？\n"
        f"候補は{count}件や。使いたいものを選んでな。"
        "\n※ 対応済みの読み取り機能は選択後にそのまま実行、"
        "書き込みは必ず確認を挟むで。"
    )
