from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

import discord

from services.capability_discovery import DiscoveryCandidate
from services.discovery_selection_executor import execute_discovery_selection
from views.community_write_view import CommunityWriteEntryView
from views.parameterized_capability_view import ParameterizedCapabilityEntryView
from views.write_capability_view import WriteCapabilityEntryView, write_capability_panel_text


# Frozen Release D contract.
WRITE_CONFIRM_DISCOVERY_IDS = frozenset({"title_set", "memory_forget", "remind"})
COMMUNITY_WRITE_DISCOVERY_IDS = frozenset({"event_create", "poll_create"})
RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS = frozenset({*WRITE_CONFIRM_DISCOVERY_IDS, *COMMUNITY_WRITE_DISCOVERY_IDS})
PARAMETERIZED_DISCOVERY_IDS = ParameterizedCapabilityEntryView.SUPPORTED


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    capability_id: str
    slash_command: str | None


SelectionCallback = Callable[[discord.Interaction, CandidateSelection], Awaitable[bool]]


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

        # Release F parameter collection is the production default path.  A custom
        # injected selection callback remains authoritative for tests/adapters and
        # preserves the pre-F fail-closed contract.
        if (
            candidate.capability_id in PARAMETERIZED_DISCOVERY_IDS
            and self._on_select is execute_discovery_selection
        ):
            view = ParameterizedCapabilityEntryView(
                requester_id=self.requester_id,
                capability_id=candidate.capability_id,
                capability_name=candidate.name,
            )
            await interaction.response.edit_message(
                content=(
                    f"**{candidate.name}** を使うんやな。\n"
                    "必要な条件だけ入力してもらって、実行前に確認するで。"
                ),
                view=view,
            )
            return

        if self._on_select is None:
            command = candidate.slash_command or candidate.name
            await interaction.response.edit_message(
                content=(
                    f"選択: **{candidate.name}**\n"
                    f"使うコマンドは `{command}` やで。\n"
                    "※ まだ自動実行はしてへんで。"
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
    if count == 1:
        return (
            "🔎 もしかして、探してる機能はこれやろか？\n"
            "下のボタンを押したら操作を始めるで。"
            "必要な確認は途中でちゃんと聞くから安心してな👌\n"
            "違ってたら「キャンセル」で戻れるで！"
        )
    return (
        "🔎 もしかして、探してる機能はこのへんやろか？\n"
        f"候補を{count}件見つけたで。使いたいものを選んでな👇\n"
        "必要な確認は途中でちゃんと聞くから安心してな。"
        "違ってたら「キャンセル」で大丈夫やで！"
    )
