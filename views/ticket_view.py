from __future__ import annotations

import io
import logging
from datetime import datetime

import discord

from config import Config, JST
from views.write_capability_view import ConfirmActionView, RequesterOnlyView


logger = logging.getLogger("AkaneBot")

TICKET_CATEGORY_NAME = "🎫｜お問い合わせ"
CATEGORY_LABELS = {
    "admin": ("管理者への相談", "🛡️"),
    "bot": ("Botの不具合", "🤖"),
    "server": ("サーバーについて", "💬"),
    "other": ("その他", "📦"),
}


def safe_channel_name(text: str) -> str:
    result = "".join(
        char for char in (text or "").lower()
        if char.isalnum() or char in {"-", "_"}
    ).strip("-_")
    return (result or "ticket")[:70]


async def create_transcript(channel: discord.TextChannel) -> bytes:
    lines = [
        "========================================",
        "Akane Bot Ticket Transcript",
        f"Guild: {channel.guild.name}",
        f"Channel: #{channel.name}",
        f"Channel ID: {channel.id}",
        f"Generated: {datetime.now(JST).isoformat()}",
        "========================================",
        "",
    ]
    try:
        async for message in channel.history(
            limit=Config.TICKET_TRANSCRIPT_LIMIT,
            oldest_first=True,
        ):
            created = message.created_at.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{created}] {message.author} ({message.author.id})")
            if message.content:
                lines.append(message.content)
            for attachment in message.attachments:
                lines.append(f"[Attachment] {attachment.url}")
            if message.embeds:
                lines.append(f"[Embeds] {len(message.embeds)}")
            lines.append("")
    except Exception as exc:
        logger.exception("Transcript generation failed: %s", exc)
        lines.append("[ERROR] Transcriptの一部取得に失敗しました。")
    return "\n".join(lines).encode("utf-8")


async def send_ticket_unlock_notifications(channel, member, unlocks: dict) -> None:
    if not Config.ACHIEVEMENT_NOTIFICATIONS:
        return
    lines: list[str] = []
    for key in unlocks.get("achievements", []):
        data = Config.ACHIEVEMENTS.get(key)
        if data:
            lines.append(f"🏆 実績解除: {data['emoji']} **{data['name']}**")
    for key in unlocks.get("titles", []):
        data = Config.TITLES.get(key)
        if data:
            lines.append(f"🎖️ 称号獲得: **{data['name']}**")
    if not lines:
        return
    try:
        await channel.send(
            content=member.mention,
            embed=discord.Embed(
                title="🎉 新しい解除項目",
                description="\n".join(lines),
                color=discord.Color.gold(),
            ),
        )
    except Exception as exc:
        logger.exception("Ticket unlock notification failed: %s", exc)


async def _ticket_settings(bot, guild_id: int) -> dict[str, int | None]:
    try:
        return await bot.db.get_ticket_settings(guild_id)
    except Exception as exc:
        logger.exception("Ticket settings lookup failed: %s", exc)
        return {"category_id": None, "staff_role_id": None}


async def is_ticket_staff(bot, member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    settings = await _ticket_settings(bot, member.guild.id)
    role_id = settings.get("staff_role_id")
    return bool(role_id and any(role.id == int(role_id) for role in member.roles))


async def _require_staff(bot, interaction: discord.Interaction) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member) or not await is_ticket_staff(bot, member):
        await interaction.response.send_message(
            "🛡️ この操作は管理者かTicket担当Staffだけ使えるで。",
            ephemeral=True,
        )
        return False
    return True


async def _ensure_ticket_category(bot, guild: discord.Guild) -> discord.CategoryChannel:
    settings = await _ticket_settings(bot, guild.id)
    category_id = settings.get("category_id")
    if category_id:
        existing = guild.get_channel(int(category_id))
        if isinstance(existing, discord.CategoryChannel):
            return existing

    category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(
            TICKET_CATEGORY_NAME,
            reason="Akane native Ticket category",
        )
    await bot.db.set_ticket_category(guild.id, category.id)
    return category


async def _ticket_overwrites(bot, guild: discord.Guild, requester: discord.Member):
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        requester: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
    }
    if guild.me is not None:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        )

    settings = await _ticket_settings(bot, guild.id)
    staff_role_id = settings.get("staff_role_id")
    if staff_role_id:
        role = guild.get_role(int(staff_role_id))
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            )
    return overwrites


async def _send_transcript_log(
    bot,
    channel: discord.TextChannel,
    ticket: dict,
    *,
    actor: discord.abc.User,
    action: str,
) -> None:
    try:
        transcript = await create_transcript(channel)
        log_id = await bot.db.get_config(channel.guild.id, "log_ch")
        log_channel = channel.guild.get_channel(log_id) if log_id else None
        if log_channel is None:
            return
        embed = discord.Embed(
            title=f"📁 Ticket {action}",
            color=discord.Color.orange(),
            timestamp=datetime.now(JST),
        )
        embed.add_field(name="Ticket", value=f"`{ticket.get('ticket_number') or ticket['id']}`", inline=True)
        embed.add_field(name="Channel", value=f"`{channel.name}`", inline=True)
        embed.add_field(name="作成者", value=f"<@{ticket['user_id']}>", inline=True)
        embed.add_field(name="実行者", value=actor.mention, inline=True)
        await log_channel.send(
            embed=embed,
            file=discord.File(io.BytesIO(transcript), filename=f"{channel.name}-transcript.txt"),
        )
    except Exception as exc:
        logger.exception("Ticket transcript log failed: %s", exc)


async def create_native_ticket(
    bot,
    interaction: discord.Interaction,
    *,
    category_key: str,
    subject: str,
    body: str,
) -> None:
    guild = interaction.guild
    requester = interaction.user
    if guild is None or not isinstance(requester, discord.Member):
        await interaction.response.send_message("この機能はサーバー内専用やで。", ephemeral=True)
        return

    existing = await bot.db.get_open_ticket(guild.id, requester.id)
    if existing:
        channel = guild.get_channel(int(existing[1]))
        if channel is not None:
            await interaction.response.send_message(
                f"📩 すでに開いてる問い合わせがあるで！\n{channel.mention}",
                ephemeral=True,
            )
            return
        await bot.db.cleanup_missing_ticket(int(existing[1]))

    await interaction.response.defer(ephemeral=True)
    channel: discord.TextChannel | None = None
    try:
        ticket_number = await bot.db.reserve_ticket_number(guild.id)
        category = await _ensure_ticket_category(bot, guild)
        overwrites = await _ticket_overwrites(bot, guild, requester)
        channel = await guild.create_text_channel(
            f"ticket-{ticket_number:04d}",
            category=category,
            overwrites=overwrites,
            reason=f"Akane native Ticket requested by {requester} ({requester.id})",
        )
        ticket_id = await bot.db.create_ticket(
            guild.id,
            channel.id,
            requester.id,
            category_key,
            ticket_number=ticket_number,
            subject=subject,
        )
        label, emoji = CATEGORY_LABELS.get(category_key, CATEGORY_LABELS["other"])
        embed = discord.Embed(
            title=f"{emoji} Ticket #{ticket_number:04d}｜{subject}",
            description=body,
            color=discord.Color.blue(),
            timestamp=datetime.now(JST),
        )
        embed.add_field(name="問い合わせ種別", value=label, inline=True)
        embed.add_field(name="作成者", value=requester.mention, inline=True)
        embed.add_field(name="状態", value="🟢 Open", inline=True)
        embed.set_footer(text="本人・管理者・設定済みStaffだけ閲覧できるで")
        await channel.send(
            content=requester.mention,
            embed=embed,
            view=TicketCloseView(bot),
        )
        await bot.db.audit_ticket(
            ticket_id=ticket_id,
            guild_id=guild.id,
            channel_id=channel.id,
            actor_id=requester.id,
            action="create",
            detail=f"category={category_key}; subject={subject}",
        )
        try:
            await bot.db.increment_ticket_count(guild.id, requester.id)
            unlocks = await bot.db.evaluate_progress_unlocks(guild.id, requester.id)
            await send_ticket_unlock_notifications(channel, requester, unlocks)
        except Exception as exc:
            logger.exception("Ticket stats failed: %s", exc)
        await interaction.followup.send(
            f"✅ 問い合わせを受け付けたで！\n{channel.mention}",
            ephemeral=True,
        )
    except Exception as exc:
        logger.exception("Native Ticket creation failed: %s", exc)
        if channel is not None:
            try:
                await channel.delete(reason="Akane Ticket creation rollback")
            except Exception:
                pass
        await interaction.followup.send(
            "Ticket作成中にエラーが起きたで。まだ問い合わせは作成されてへんで。",
            ephemeral=True,
        )


class TicketCreateModal(discord.ui.Modal, title="問い合わせを作成"):
    subject = discord.ui.TextInput(
        label="件名",
        placeholder="例: 管理人に相談したいことがあります",
        min_length=1,
        max_length=100,
    )
    body = discord.ui.TextInput(
        label="問い合わせ内容",
        style=discord.TextStyle.paragraph,
        placeholder="できるだけ具体的に書いてな",
        min_length=1,
        max_length=1800,
    )

    def __init__(self, bot, *, requester_id: int, category_key: str = "admin") -> None:
        super().__init__()
        self.bot = bot
        self.requester_id = requester_id
        self.category_key = category_key

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("この操作は本人だけ使えるで。", ephemeral=True)
            return
        subject = str(self.subject.value).strip()
        body = str(self.body.value).strip()
        label, emoji = CATEGORY_LABELS.get(self.category_key, CATEGORY_LABELS["other"])

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await create_native_ticket(
                self.bot,
                confirm_interaction,
                category_key=self.category_key,
                subject=subject,
                body=body,
            )

        await interaction.response.send_message(
            f"🎫 **{label}**\n**件名:** {subject}\n\n{body}\n\nこの内容で管理側に送る？",
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="問い合わせを送信",
            ),
            ephemeral=True,
        )


class TicketCreateEntryView(RequesterOnlyView):
    """Natural-language entry to the same native Ticket system as the panel."""

    def __init__(self, bot, *, requester_id: int, category_key: str = "admin") -> None:
        super().__init__(requester_id=requester_id)
        self.bot = bot
        self.category_key = category_key

    async def begin(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.message.edit(
            content="🎫 管理人への問い合わせやな。茜が受付するで！内容を入力してな👇",
            view=None,
        )
        await interaction.response.send_modal(
            TicketCreateModal(
                self.bot,
                requester_id=self.requester_id,
                category_key=self.category_key,
            )
        )


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot) -> None:
        self.bot = bot
        options = [
            discord.SelectOption(label="管理者への相談", description="管理者に相談したいことがある", emoji="🛡️", value="admin"),
            discord.SelectOption(label="Botの不具合", description="茜Botの不具合・エラーなど", emoji="🤖", value="bot"),
            discord.SelectOption(label="サーバーについて", description="サーバー運営やルールについて", emoji="💬", value="server"),
            discord.SelectOption(label="その他", description="上記に当てはまらない問い合わせ", emoji="📦", value="other"),
        ]
        super().__init__(
            placeholder="問い合わせの種類を選んでな",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("この機能はサーバー内専用やで。", ephemeral=True)
            return
        existing = await self.bot.db.get_open_ticket(interaction.guild.id, interaction.user.id)
        if existing:
            channel = interaction.guild.get_channel(int(existing[1]))
            if channel:
                await interaction.response.send_message(
                    f"📩 すでに開いてる問い合わせがあるで！\n{channel.mention}",
                    ephemeral=True,
                )
                return
        await interaction.response.send_modal(
            TicketCreateModal(
                self.bot,
                requester_id=interaction.user.id,
                category_key=self.values[0],
            )
        )


class TicketStaffRoleSelect(discord.ui.RoleSelect):
    def __init__(self, bot, requester_id: int) -> None:
        super().__init__(placeholder="Ticket担当Staffロールを選択", min_values=1, max_values=1)
        self.bot = bot
        self.requester_id = requester_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("この操作は設定を始めた管理者だけ使えるで。", ephemeral=True)
            return
        role = self.values[0]
        await self.bot.db.set_ticket_staff_role(interaction.guild.id, role.id)
        await interaction.response.edit_message(
            content=f"✅ Ticket担当Staffを {role.mention} に設定したで。",
            view=None,
        )


class TicketStaffRoleView(RequesterOnlyView):
    def __init__(self, bot, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        self.add_item(TicketStaffRoleSelect(bot, requester_id))


class TicketView(discord.ui.View):
    """Persistent public Ticket panel. Compatible with existing setup panels."""

    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TicketCategorySelect(bot))

        staff = discord.ui.Button(
            label="Staff設定",
            emoji="⚙️",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_staff_settings",
        )

        async def staff_callback(interaction: discord.Interaction) -> None:
            if interaction.guild is None or not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("⛔ この設定は管理者専用やで。", ephemeral=True)
                return
            await interaction.response.send_message(
                "🛡️ Ticketを担当できるStaffロールを選んでな。Administratorは常に操作できるで。",
                view=TicketStaffRoleView(self.bot, requester_id=interaction.user.id),
                ephemeral=True,
            )

        staff.callback = staff_callback
        self.add_item(staff)


class TicketCloseConfirmView(RequesterOnlyView):
    def __init__(self, bot, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id, timeout=Config.TICKET_CLOSE_CONFIRM_TIMEOUT)
        self.bot = bot
        confirm = discord.ui.Button(label="閉じる", emoji="🔒", style=discord.ButtonStyle.danger)
        cancel = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary)

        async def confirm_callback(interaction: discord.Interaction) -> None:
            ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
            if not ticket or ticket["status"] != "open":
                await interaction.response.edit_message(content="このTicketはOpen状態やないで。", view=None)
                return
            channel = interaction.channel
            await _send_transcript_log(self.bot, channel, ticket, actor=interaction.user, action="Closed")
            await self.bot.db.close_ticket(channel.id)
            requester = interaction.guild.get_member(int(ticket["user_id"]))
            if requester is not None:
                overwrite = channel.overwrites_for(requester)
                overwrite.send_messages = False
                overwrite.view_channel = True
                await channel.set_permissions(requester, overwrite=overwrite, reason="Akane Ticket closed")
            number = ticket.get("ticket_number") or ticket["id"]
            try:
                await channel.edit(name=f"closed-{int(number):04d}", reason="Akane Ticket closed")
            except Exception:
                pass
            await self.bot.db.audit_ticket(
                ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=channel.id,
                actor_id=interaction.user.id, action="close",
            )
            await interaction.response.edit_message(
                content="🔒 Ticketを閉じたで。チャンネルは残してあるから、Staffが必要なら再開できるで。",
                view=None,
            )
            await channel.send("🔒 **Closed**｜解決済みにしたで。Staffは下の「再開」から戻せるで。", view=TicketCloseView(self.bot))

        async def cancel_callback(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(content="👌 閉じるのをキャンセルしたで。", view=None)

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)


class TicketRenameModal(discord.ui.Modal, title="Ticket名を変更"):
    name = discord.ui.TextInput(label="新しい名前", placeholder="例: bot-error", min_length=1, max_length=60)

    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await _require_staff(self.bot, interaction):
            return
        ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        cleaned = safe_channel_name(str(self.name.value))
        number = ticket.get("ticket_number") or ticket["id"]
        prefix = "closed" if ticket["status"] == "closed" else "ticket"
        await interaction.channel.edit(name=f"{prefix}-{int(number):04d}-{cleaned}", reason="Akane Ticket renamed")
        await self.bot.db.audit_ticket(
            ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=interaction.channel.id,
            actor_id=interaction.user.id, action="rename", detail=cleaned,
        )
        await interaction.response.send_message("✅ Ticket名を変更したで。", ephemeral=True)


class TicketMemberSelect(discord.ui.UserSelect):
    def __init__(self, bot, *, mode: str) -> None:
        super().__init__(placeholder="メンバーを選んでな", min_values=1, max_values=1)
        self.bot = bot
        self.mode = mode

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _require_staff(self.bot, interaction):
            return
        ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        user = self.values[0]
        member = interaction.guild.get_member(user.id)
        if member is None:
            await interaction.response.send_message("そのメンバーがサーバーに見つからへんで。", ephemeral=True)
            return
        if self.mode == "add":
            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=ticket["status"] == "open",
                read_message_history=True,
                attach_files=True,
                reason="Akane Ticket member added",
            )
            await self.bot.db.add_ticket_member(ticket["id"], member.id)
            action = "member_add"
            message = f"✅ {member.mention} をTicketに追加したで。"
        else:
            if member.id == int(ticket["user_id"]):
                await interaction.response.send_message("作成者本人は追加メンバーから外せへんで。", ephemeral=True)
                return
            await interaction.channel.set_permissions(member, overwrite=None, reason="Akane Ticket member removed")
            await self.bot.db.remove_ticket_member(ticket["id"], member.id)
            action = "member_remove"
            message = f"✅ {member.mention} をTicketから外したで。"
        await self.bot.db.audit_ticket(
            ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=interaction.channel.id,
            actor_id=interaction.user.id, action=action, detail=str(member.id),
        )
        await interaction.response.edit_message(content=message, view=None)


class TicketMemberSelectView(RequesterOnlyView):
    def __init__(self, bot, *, requester_id: int, mode: str) -> None:
        super().__init__(requester_id=requester_id)
        self.add_item(TicketMemberSelect(bot, mode=mode))


class TicketDeleteConfirmView(RequesterOnlyView):
    def __init__(self, bot, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        self.bot = bot
        confirm = discord.ui.Button(label="完全に削除", style=discord.ButtonStyle.danger, emoji="🗑️")
        cancel = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary)

        async def confirm_callback(interaction: discord.Interaction) -> None:
            if not await _require_staff(self.bot, interaction):
                return
            ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
            if not ticket:
                await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
                return
            await _send_transcript_log(self.bot, interaction.channel, ticket, actor=interaction.user, action="Deleted")
            await self.bot.db.audit_ticket(
                ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=interaction.channel.id,
                actor_id=interaction.user.id, action="delete",
            )
            await self.bot.db.mark_ticket_deleted(interaction.channel.id)
            await interaction.response.send_message("🗑️ Ticketを削除するで。", ephemeral=True)
            await interaction.channel.delete(reason=f"Akane Ticket deleted by {interaction.user}")

        async def cancel_callback(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(content="👌 削除をキャンセルしたで。", view=None)

        confirm.callback = confirm_callback
        cancel.callback = cancel_callback
        self.add_item(confirm)
        self.add_item(cancel)


class TicketManageView(RequesterOnlyView):
    def __init__(self, bot, *, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        self.bot = bot
        for label, emoji, action in (
            ("名前変更", "✏️", "rename"),
            ("メンバー追加", "➕", "add"),
            ("メンバー削除", "➖", "remove"),
            ("完全削除", "🗑️", "delete"),
        ):
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)

            async def callback(interaction: discord.Interaction, *, selected=action) -> None:
                if not await _require_staff(self.bot, interaction):
                    return
                if selected == "rename":
                    await interaction.response.send_modal(TicketRenameModal(self.bot))
                elif selected in {"add", "remove"}:
                    await interaction.response.edit_message(
                        content="👤 対象メンバーを選んでな。",
                        view=TicketMemberSelectView(self.bot, requester_id=self.requester_id, mode=selected),
                    )
                else:
                    await interaction.response.edit_message(
                        content="⚠️ このTicketチャンネルを完全に削除する？Transcriptは監査ログへ送るで。",
                        view=TicketDeleteConfirmView(self.bot, requester_id=self.requester_id),
                    )

            button.callback = callback
            self.add_item(button)


class TicketCloseView(discord.ui.View):
    """Persistent Ticket controls. Historical close custom_id is preserved."""

    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="閉じる",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close_button",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("このチャンネルはTicketとして登録されてへんみたいや。", ephemeral=True)
            return
        is_owner = interaction.user.id == int(ticket["user_id"])
        is_staff = isinstance(interaction.user, discord.Member) and await is_ticket_staff(self.bot, interaction.user)
        if not (is_owner or is_staff):
            await interaction.response.send_message("このTicketを閉じられるんは作成者かStaffだけやで。", ephemeral=True)
            return
        if ticket["status"] != "open":
            await interaction.response.send_message("このTicketはすでに閉じられてるで。", ephemeral=True)
            return
        await interaction.response.send_message(
            "⚠️ このTicketを解決済みにして閉じる？チャンネルは削除せず、あとでStaffが再開できるで。",
            view=TicketCloseConfirmView(self.bot, requester_id=interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label="担当する", style=discord.ButtonStyle.primary, emoji="🙋", custom_id="ticket_claim_button")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(self.bot, interaction):
            return
        ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        await self.bot.db.claim_ticket(interaction.channel.id, interaction.user.id)
        await self.bot.db.audit_ticket(
            ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=interaction.channel.id,
            actor_id=interaction.user.id, action="claim",
        )
        await interaction.response.send_message(f"🙋 {interaction.user.mention} がこのTicketを担当するで。")

    @discord.ui.button(label="再開", style=discord.ButtonStyle.success, emoji="🔓", custom_id="ticket_reopen_button")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(self.bot, interaction):
            return
        ticket = await self.bot.db.get_native_ticket(interaction.channel.id)
        if not ticket or ticket["status"] != "closed":
            await interaction.response.send_message("このTicketはClosed状態やないで。", ephemeral=True)
            return
        await self.bot.db.reopen_ticket(interaction.channel.id)
        requester = interaction.guild.get_member(int(ticket["user_id"]))
        if requester is not None:
            overwrite = interaction.channel.overwrites_for(requester)
            overwrite.view_channel = True
            overwrite.send_messages = True
            overwrite.read_message_history = True
            await interaction.channel.set_permissions(requester, overwrite=overwrite, reason="Akane Ticket reopened")
        for user_id in await self.bot.db.list_ticket_members(ticket["id"]):
            member = interaction.guild.get_member(user_id)
            if member is not None:
                overwrite = interaction.channel.overwrites_for(member)
                overwrite.view_channel = True
                overwrite.send_messages = True
                overwrite.read_message_history = True
                await interaction.channel.set_permissions(member, overwrite=overwrite, reason="Akane Ticket reopened")
        number = ticket.get("ticket_number") or ticket["id"]
        try:
            await interaction.channel.edit(name=f"ticket-{int(number):04d}", reason="Akane Ticket reopened")
        except Exception:
            pass
        await self.bot.db.audit_ticket(
            ticket_id=ticket["id"], guild_id=interaction.guild.id, channel_id=interaction.channel.id,
            actor_id=interaction.user.id, action="reopen",
        )
        await interaction.response.send_message("🔓 Ticketを再開したで。作成者もまた書き込めるようになったで。")

    @discord.ui.button(label="管理", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="ticket_manage_button")
    async def manage(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(self.bot, interaction):
            return
        await interaction.response.send_message(
            "⚙️ Ticket管理メニューやで。",
            view=TicketManageView(self.bot, requester_id=interaction.user.id),
            ephemeral=True,
        )
