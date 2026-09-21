from __future__ import annotations

import discord
from discord import app_commands

from views.write_capability_view import RequesterOnlyView


async def _general_cog(interaction: discord.Interaction):
    cog = interaction.client.get_cog("GeneralCog")
    if cog is None:
        raise RuntimeError("GeneralCog unavailable")
    return cog


class ExecuteConfirmView(RequesterOnlyView):
    def __init__(self, *, requester_id: int, on_confirm, confirm_label: str = "実行する") -> None:
        super().__init__(requester_id=requester_id)
        confirm = discord.ui.Button(label=confirm_label, style=discord.ButtonStyle.primary, custom_id="param_exec:confirm")
        cancel = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary, custom_id="param_exec:cancel")

        async def confirm_callback(interaction: discord.Interaction) -> None:
            self.disable_all()
            self.stop()
            await on_confirm(interaction)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(content="キャンセル済みやで。実行はしてへんで。", view=self)

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)


class SearchModal(discord.ui.Modal, title="メッセージ検索"):
    keyword = discord.ui.TextInput(label="検索キーワード", min_length=1, max_length=100)
    days = discord.ui.TextInput(label="何日前まで？（任意）", placeholder="例: 7", required=False, max_length=4)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        keyword = str(self.keyword.value).strip()
        days_text = str(self.days.value).strip()
        try:
            days = int(days_text) if days_text else None
        except ValueError:
            await interaction.response.send_message("日数は数字で入力してな。", ephemeral=True)
            return
        if days is not None and (days < 1 or days > 3650):
            await interaction.response.send_message("日数は1〜3650日の範囲で入力してな。", ephemeral=True)
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            cog = await _general_cog(confirm_interaction)
            await cog.search.callback(cog, confirm_interaction, keyword, None, None, days)

        period = f"過去{days}日" if days else "期間指定なし"
        await interaction.response.send_message(
            f"現在のチャンネルから **{keyword}** を検索するで。範囲: {period}",
            view=ExecuteConfirmView(requester_id=self.requester_id, on_confirm=execute, confirm_label="検索する"),
            ephemeral=True,
        )


class TranslateModal(discord.ui.Modal, title="AI翻訳"):
    language = discord.ui.TextInput(label="翻訳先の言語", placeholder="例: English / 日本語", min_length=1, max_length=50)
    text = discord.ui.TextInput(label="翻訳する文章", style=discord.TextStyle.paragraph, min_length=1, max_length=2000)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        language = str(self.language.value).strip()
        text = str(self.text.value).strip()

        async def execute(confirm_interaction: discord.Interaction) -> None:
            cog = await _general_cog(confirm_interaction)
            await cog.translate.callback(cog, confirm_interaction, language, text)

        await interaction.response.send_message(
            f"**{language}** へAI翻訳するで。外部AI処理は確定後にだけ実行するで。",
            view=ExecuteConfirmView(requester_id=self.requester_id, on_confirm=execute, confirm_label="AI翻訳を実行"),
            ephemeral=True,
        )


class DefineModal(discord.ui.Modal, title="AI辞書"):
    word = discord.ui.TextInput(label="調べる語・概念", min_length=1, max_length=200)
    wiki = discord.ui.TextInput(label="Wiki Mode（任意）", placeholder="yes / no", required=False, max_length=5)

    def __init__(self, *, requester_id: int) -> None:
        super().__init__()
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        word = str(self.word.value).strip()
        wiki_text = str(self.wiki.value).strip().lower()
        if wiki_text not in {"", "no", "n", "false", "0", "yes", "y", "true", "1"}:
            await interaction.response.send_message("Wiki Modeは yes / no で入力してな。", ephemeral=True)
            return
        wiki_mode = wiki_text in {"yes", "y", "true", "1"}

        async def execute(confirm_interaction: discord.Interaction) -> None:
            cog = await _general_cog(confirm_interaction)
            await cog.define.callback(cog, confirm_interaction, word, wiki_mode)

        await interaction.response.send_message(
            f"**{word}** をAI辞書で調べるで。Wiki Mode: {'ON' if wiki_mode else 'OFF'}",
            view=ExecuteConfirmView(requester_id=self.requester_id, on_confirm=execute, confirm_label="AI辞書を実行"),
            ephemeral=True,
        )


class SummaryCountView(RequesterOnlyView):
    def __init__(self, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        for count in (5, 10, 20):
            button = discord.ui.Button(label=f"直近{count}件", style=discord.ButtonStyle.secondary, custom_id=f"summary_count:{count}")

            async def callback(interaction: discord.Interaction, *, selected=count) -> None:
                async def execute(confirm_interaction: discord.Interaction) -> None:
                    cog = await _general_cog(confirm_interaction)
                    await cog.summary.callback(cog, confirm_interaction, selected)

                await interaction.response.edit_message(
                    content=f"自分の直近 **{selected}件** の発言をAI要約するで。",
                    view=ExecuteConfirmView(requester_id=self.requester_id, on_confirm=execute, confirm_label="AI要約を実行"),
                )
                self.stop()

            button.callback = callback
            self.add_item(button)


class RankingsView(RequesterOnlyView):
    CHOICES = (
        ("🔥 週間XP", "weekly"),
        ("💬 発言数", "messages"),
        ("🤖 AI会話", "ai"),
        ("🏆 実績数", "achievements"),
    )

    def __init__(self, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        for label, value in self.CHOICES:
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"rankings:{value}")

            async def callback(interaction: discord.Interaction, *, selected=value, selected_label=label) -> None:
                cog = await _general_cog(interaction)
                choice = app_commands.Choice(name=selected_label, value=selected)
                await cog.rankings.callback(cog, interaction, choice)
                self.stop()

            button.callback = callback
            self.add_item(button)


class ParameterizedCapabilityEntryView(RequesterOnlyView):
    SUPPORTED = frozenset({"message_search", "translate", "define", "summary", "rankings", "fortune", "titles"})

    def __init__(self, *, requester_id: int, capability_id: str, capability_name: str) -> None:
        super().__init__(requester_id=requester_id)
        self.capability_id = capability_id
        self.capability_name = capability_name
        start = discord.ui.Button(label=capability_name[:80], style=discord.ButtonStyle.secondary, custom_id=f"param_entry:{capability_id}")
        cancel = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary, custom_id="param_entry:cancel")

        async def start_callback(interaction: discord.Interaction) -> None:
            self.disable_all()
            self.stop()
            cid = self.capability_id
            if cid == "message_search":
                await interaction.response.send_modal(SearchModal(requester_id=self.requester_id))
                return
            if cid == "translate":
                await interaction.response.send_modal(TranslateModal(requester_id=self.requester_id))
                return
            if cid == "define":
                await interaction.response.send_modal(DefineModal(requester_id=self.requester_id))
                return
            if cid == "summary":
                await interaction.response.edit_message(content="要約する発言数を選んでな。", view=SummaryCountView(requester_id=self.requester_id))
                return
            if cid == "rankings":
                await interaction.response.edit_message(content="ランキングの種類を選んでな。", view=RankingsView(requester_id=self.requester_id))
                return
            if cid in {"fortune", "titles"}:
                async def execute(confirm_interaction: discord.Interaction) -> None:
                    cog = await _general_cog(confirm_interaction)
                    command = cog.fortune if cid == "fortune" else cog.titles
                    await command.callback(cog, confirm_interaction)
                note = "初回表示では今日の運勢を保存するで。" if cid == "fortune" else "称号の解除状況を更新してから表示するで。"
                await interaction.response.edit_message(
                    content=f"**{self.capability_name}** を実行する？\n{note}",
                    view=ExecuteConfirmView(requester_id=self.requester_id, on_confirm=execute),
                )
                return
            await interaction.response.send_message("この機能は引数収集フロー対象外やで。", ephemeral=True)

        async def cancel_callback(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(content="キャンセル済みやで。実行はしてへんで。", view=self)

        start.callback = start_callback
        cancel.callback = cancel_callback
        self.add_item(start)
        self.add_item(cancel)
