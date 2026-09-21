from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

import discord

from services.capability_discovery import DiscoveryCandidate
from services.discovery_selection_executor import execute_discovery_selection
from views.community_write_view import CommunityWriteEntryView
from views.parameterized_capability_view import ParameterizedCapabilityEntryView
from views.ticket_view import TicketCreateEntryView
from views.write_capability_view import WriteCapabilityEntryView


# Frozen Release D/E execution boundaries. The UX may become shorter, but these
# capabilities still keep their existing confirmation and authorization rules.
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
    """Requester-only discovery panel.

    A capability button starts that capability immediately. The old extra
    "same capability again" entry button was redundant and has been removed.
    State-changing operations still have their separate final confirmation.
    """

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
        self._candidates = tuple(candidates)[:4]

        for candidate in self._candidates:
            button = discord.ui.Button(
                label=candidate.name[:80],
                style=(
                    discord.ButtonStyle.primary
                    if len(self._candidates) == 1
                    else discord.ButtonStyle.secondary
                ),
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
            "この操作はリクエストした本人だけ使えるで。",
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

        # Ticket is a native interaction entry outside the 18-capability slash
        # catalog. Selection opens content collection; no channel is created
        # until the later explicit final confirmation.
        if candidate.capability_id == "ticket_create":
            view = TicketCreateEntryView(
                interaction.client,
                requester_id=self.requester_id,
                category_key="admin",
            )
            await view.begin(interaction)
            return

        # Selecting a discovered write capability only starts argument/scope
        # collection. Mutation is still impossible until its later confirmation.
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
            await view.begin(interaction)
            return

        # Parameterized capabilities likewise jump straight to their real input
        # UI instead of asking the user to press an identical capability button.
        # A custom injected callback remains authoritative for tests/adapters.
        if (
            candidate.capability_id in PARAMETERIZED_DISCOVERY_IDS
            and self._on_select is execute_discovery_selection
        ):
            view = ParameterizedCapabilityEntryView(
                requester_id=self.requester_id,
                capability_id=candidate.capability_id,
                capability_name=candidate.name,
            )
            await view.begin(interaction)
            return

        if self._on_select is None:
            command = candidate.slash_command or candidate.name
            await interaction.response.edit_message(
                content=(
                    f"✨ **{candidate.name}** やな。\n"
                    f"この画面からは自動実行せえへんから、必要なら `{command}` を使ってな。"
                ),
                view=self,
            )
            return

        executed = await self._on_select(interaction, self.selection)
        if executed:
            content = f"✅ **{candidate.name}** を実行したで。"
        else:
            command = candidate.slash_command or candidate.name
            content = (
                f"✨ **{candidate.name}** やな。\n"
                "この機能はこの画面から直接は実行せえへんで。\n"
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
            content="👌 キャンセルしたで。何も実行してへんから安心してな。",
            view=self,
        )
        self.stop()


def candidate_panel_text(candidates: Sequence[DiscoveryCandidate]) -> str:
    visible = tuple(candidates)[:4]
    count = len(visible)
    if count <= 1:
        return (
            "🔎 もしかして、探してる機能はこれやろか？\n"
            "下のボタンを押したら操作を始めるで。必要な変更は途中でちゃんと確認するから安心してな👌\n"
            "違ってたらキャンセルで大丈夫やで。"
        )
    return (
        "🔎 もしかして、探してる機能はこのへんやろか？\n"
        f"候補が **{count}件** あるから、使いたいものを選んでな👇\n"
        "ボタンを押したらその操作を始めるで。違ってたらキャンセルでも大丈夫やで👌"
    )
