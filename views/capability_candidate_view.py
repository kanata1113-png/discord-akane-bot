from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

import discord

from services.capability_discovery import DiscoveryCandidate
from services.discovery_selection_executor import execute_discovery_selection
from views.community_write_view import (
    CommunityWriteEntryView,
    EventTypeChoiceView,
    PollCreateModal,
)
from views.parameterized_capability_view import ParameterizedCapabilityEntryView
from views.ticket_native_v4 import TicketCreateEntryView
from views.write_capability_view import (
    ForgetScopeView,
    RemindModal,
    TitleSetModal,
    WriteCapabilityEntryView,
)


# Historical groups remain stable; Ticket is the dogfood-era native write flow.
WRITE_CONFIRM_DISCOVERY_IDS = frozenset({"title_set", "memory_forget", "remind"})
COMMUNITY_WRITE_DISCOVERY_IDS = frozenset({"event_create", "poll_create"})
NATIVE_TICKET_DISCOVERY_IDS = frozenset({"ticket_create"})
RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS = frozenset(
    {*WRITE_CONFIRM_DISCOVERY_IDS, *COMMUNITY_WRITE_DISCOVERY_IDS, *NATIVE_TICKET_DISCOVERY_IDS}
)
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

        # Selecting a WRITE_CONFIRM candidate starts argument/scope collection
        # immediately. It never skips the final mutation confirmation.
        if candidate.capability_id in RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS:
            if candidate.capability_id == "ticket_create":
                await interaction.response.edit_message(
                    content=(
                        "🎫 管理人・運営への問い合わせやな！茜が受付するで。\n"
                        "まず種類を選んでな👇 送信前に内容確認もできるで👌"
                    ),
                    view=TicketCreateEntryView(
                        bot=interaction.client,
                        requester_id=self.requester_id,
                    ),
                )
                return

            if candidate.capability_id == "event_create":
                await interaction.response.edit_message(
                    content=(
                        "📅 イベント作成やな！開催形式を選んでな👇\n"
                        "最後に内容を確認してから作成するから、ここではまだ登録されへんで👌"
                    ),
                    view=EventTypeChoiceView(requester_id=self.requester_id),
                )
                return

            if candidate.capability_id == "memory_forget":
                await interaction.response.edit_message(
                    content="🧹 削除する会話履歴の範囲を選んでな。最後にもう一度確認するで。",
                    view=ForgetScopeView(requester_id=self.requester_id),
                )
                return

            if candidate.capability_id == "title_set":
                await interaction.message.edit(
                    content="🎖️ 変更したい称号を入力してな。確定までは変更されへんで👌",
                    view=self,
                )
                await interaction.response.send_modal(
                    TitleSetModal(requester_id=self.requester_id)
                )
                return

            if candidate.capability_id == "remind":
                await interaction.message.edit(
                    content="⏰ リマインダーの内容を入力してな。登録前にちゃんと確認するで👌",
                    view=self,
                )
                await interaction.response.send_modal(
                    RemindModal(requester_id=self.requester_id)
                )
                return

            if candidate.capability_id == "poll_create":
                await interaction.message.edit(
                    content="📊 投票内容を入力してな。作成前に最終確認するで👌",
                    view=self,
                )
                await interaction.response.send_modal(
                    PollCreateModal(requester_id=self.requester_id)
                )
                return

            await interaction.response.edit_message(
                content=(
                    f"✨ **{candidate.name}** やな！\n"
                    "下のボタンから操作を始めてな。最終確認までは何も変更されへんで👌"
                ),
                view=(
                    CommunityWriteEntryView(
                        requester_id=self.requester_id,
                        capability_id=candidate.capability_id,
                        capability_name=candidate.name,
                    )
                    if candidate.capability_id in COMMUNITY_WRITE_DISCOVERY_IDS
                    else WriteCapabilityEntryView(
                        requester_id=self.requester_id,
                        capability_id=candidate.capability_id,
                        capability_name=candidate.name,
                    )
                ),
            )
            return

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
                    f"✨ **{candidate.name}** やな！\n"
                    "必要な条件だけ聞くから、下のボタンから進んでな👇"
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
                "キャンセルしたで👌\n"
                "何も変更してへんから安心してな。"
            ),
            view=self,
        )
        self.stop()


def candidate_panel_text(candidates: Sequence[DiscoveryCandidate]) -> str:
    count = min(len(tuple(candidates)), 4)
    if count == 1:
        return (
            "🔎 もしかして、探してる機能はこれやろか？\n"
            "下のボタンを押したら操作を始めるで。必要な確認は途中でちゃんと聞くから安心してな👌\n"
            "違ってたらキャンセルでも大丈夫やで！"
        )
    return (
        "🔎 もしかして、探してる機能はこのへんやろか？\n"
        f"候補を{count}件見つけたで。使いたいものを下から選んでな👇\n"
        "必要な確認は途中でちゃんと聞くで。違ってたらキャンセルでも大丈夫や！"
    )


def single_candidate_handoff(
    candidate: DiscoveryCandidate,
    *,
    requester_id: int,
    bot=None,
) -> tuple[str, discord.ui.View]:
    """Build operation-specific entry UI for a single unambiguous candidate."""

    if candidate.capability_id == "ticket_create" and bot is not None:
        return (
            "🎫 管理人・運営への問い合わせやな！茜が受付するで。\n"
            "種類を選んで、問い合わせ内容を書いてな👇 送る前に確認できるで👌",
            TicketCreateEntryView(bot=bot, requester_id=requester_id),
        )

    if candidate.capability_id == "event_create":
        return (
            "📅 イベント作成やな！開催形式を選んでな👇\n"
            "最後に内容を確認してから作成するから、ここで押しても急に登録はされへんで👌",
            EventTypeChoiceView(requester_id=requester_id),
        )

    if candidate.capability_id in RELEASE_E_WRITE_CONFIRM_DISCOVERY_IDS:
        if candidate.capability_id in COMMUNITY_WRITE_DISCOVERY_IDS:
            view: discord.ui.View = CommunityWriteEntryView(
                requester_id=requester_id,
                capability_id=candidate.capability_id,
                capability_name=candidate.name,
            )
        else:
            view = WriteCapabilityEntryView(
                requester_id=requester_id,
                capability_id=candidate.capability_id,
                capability_name=candidate.name,
            )
        return (
            f"✨ **{candidate.name}** やな！\n"
            "下のボタンを押したら操作を始めるで。最終確認までは何も変更されへんから安心してな👌",
            view,
        )

    if candidate.capability_id in PARAMETERIZED_DISCOVERY_IDS:
        return (
            f"✨ **{candidate.name}** やな！\n"
            "必要な条件だけ聞くから、下のボタンから進んでな👇",
            ParameterizedCapabilityEntryView(
                requester_id=requester_id,
                capability_id=candidate.capability_id,
                capability_name=candidate.name,
            ),
        )

    return (
        "🔎 探してる機能、たぶんこれやと思うで！\n"
        "下のボタンを押したら始めるで。違ってたらキャンセルしてな👌",
        CapabilityCandidateView((candidate,), requester_id=requester_id),
    )
