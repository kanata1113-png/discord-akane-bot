from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import discord

from services.native_ticket_store import NativeTicketRecord, NativeTicketStore
from views.ticket_view import create_transcript, send_ticket_unlock_notifications
from views.write_capability_view import ConfirmActionView, RequesterOnlyView


logger = logging.getLogger("AkaneBot")
DEFAULT_TICKET_CATEGORY_NAME = "🎫｜お問い合わせ"


CATEGORY_LABELS = {
    "admin": ("🛡️", "管理者への相談"),
    "bot": ("🤖", "Botの不具合"),
    "server": ("💬", "サーバーについて"),
    "other": ("📦", "その他"),
}


def _store(bot) -> NativeTicketStore:
    return NativeTicketStore(bot.db.path)


async def _staff_role(guild: discord.Guild, bot) -> discord.Role | None:
    _, role_id = await _store(bot).settings(guild.id)
    return guild.get_role(role_id) if role_id else None


async def is_ticket_staff(interaction: discord.Interaction, bot) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    role = await _staff_role(interaction.guild, bot) if interaction.guild else None
    return role is not None and role in member.roles


async def _require_staff(interaction: discord.Interaction, bot) -> bool:
    if await is_ticket_staff(interaction, bot):
        return True
    await interaction.response.send_message(
        "🛡️ この操作はTicket担当者か管理者だけ使えるで。",
        ephemeral=True,
    )
    return False


async def ensure_ticket_category(guild: discord.Guild, bot) -> discord.CategoryChannel:
    store = _store(bot)
    category_id, staff_role_id = await store.settings(guild.id)
    category = guild.get_channel(category_id) if category_id else None
    if isinstance(category, discord.CategoryChannel):
        return category

    category = discord.utils.get(guild.categories, name=DEFAULT_TICKET_CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(
            DEFAULT_TICKET_CATEGORY_NAME,
            reason="Akane Native Ticket category",
        )
    await store.set_settings(
        guild.id,
        category_id=category.id,
        staff_role_id=staff_role_id,
    )
    return category


def _ticket_channel_name(number: int, *, closed: bool = False) -> str:
    prefix = "closed" if closed else "ticket"
    return f"{prefix}-{number:04d}"


async def create_native_ticket(
    interaction: discord.Interaction,
    *,
    bot,
    category_key: str,
    subject: str,
    description: str,
) -> discord.TextChannel:
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member):
        raise ValueError("guild_required")

    store = _store(bot)
    existing = await store.get_open_for_user(guild.id, interaction.user.id)
    if existing is not None:
        channel = guild.get_channel(existing.channel_id)
        if channel is not None:
            raise ValueError(f"open_ticket_exists:{channel.id}")
        await store.set_status(existing.id, "closed")

    category = await ensure_ticket_category(guild, bot)
    _, staff_role_id = await store.settings(guild.id)
    staff_role = guild.get_role(staff_role_id) if staff_role_id else None
    bot_member = guild.me

    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
    }
    if bot_member is not None:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        )
    if staff_role is not None:
        overwrites[staff_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        )

    number = await store.allocate_number(guild.id)
    channel = await guild.create_text_channel(
        _ticket_channel_name(number),
        category=category,
        overwrites=overwrites,
        topic=f"Akane Ticket #{number:04d} | requester={interaction.user.id}",
        reason=f"Akane Native Ticket requested by {interaction.user} ({interaction.user.id})",
    )

    try:
        ticket_id = await store.create(
            guild_id=guild.id,
            channel_id=channel.id,
            user_id=interaction.user.id,
            category=category_key,
            ticket_number=number,
            subject=subject,
            description=description,
        )
    except Exception:
        await channel.delete(reason="Akane Native Ticket DB create rollback")
        raise

    await store.audit(ticket_id, interaction.user.id, "create", subject)
    emoji, category_label = CATEGORY_LABELS.get(category_key, CATEGORY_LABELS["other"])
    embed = discord.Embed(
        title=f"{emoji} Ticket #{number:04d} — {subject}",
        description=description,
        color=discord.Color.blue(),
    )
    embed.add_field(name="問い合わせ種別", value=category_label, inline=True)
    embed.add_field(name="作成者", value=interaction.user.mention, inline=True)
    if staff_role is not None:
        embed.add_field(name="担当Role", value=staff_role.mention, inline=True)
    embed.set_footer(text="解決したら「閉じる」を押してな。Ticketは削除せず保管できるで。")

    mention = interaction.user.mention
    if staff_role is not None:
        mention += f" {staff_role.mention}"
    await channel.send(
        content=mention,
        embed=embed,
        view=TicketOpenView(bot),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )

    try:
        await bot.db.increment_ticket_count(guild.id, interaction.user.id)
        unlocks = await bot.db.evaluate_progress_unlocks(guild.id, interaction.user.id)
        await send_ticket_unlock_notifications(channel, interaction.user, unlocks)
    except Exception as exc:
        logger.exception("Native ticket progress stats failed: %s", exc)

    return channel


class TicketCreateModal(discord.ui.Modal, title="問い合わせ内容"):
    subject = discord.ui.TextInput(
        label="件名",
        placeholder="例：サーバールールについて相談",
        min_length=1,
        max_length=100,
    )
    description = discord.ui.TextInput(
        label="問い合わせ内容",
        placeholder="できるだけ具体的に書いてな",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=1500,
    )

    def __init__(self, *, bot, requester_id: int, category_key: str) -> None:
        super().__init__()
        self.bot = bot
        self.requester_id = requester_id
        self.category_key = category_key

    async def on_submit(self, interaction: discord.Interaction) -> None:
        subject = str(self.subject.value).strip()
        description = str(self.description.value).strip()
        emoji, label = CATEGORY_LABELS.get(self.category_key, CATEGORY_LABELS["other"])

        async def execute(confirm_interaction: discord.Interaction) -> None:
            try:
                await confirm_interaction.response.defer(ephemeral=True)
                channel = await create_native_ticket(
                    confirm_interaction,
                    bot=self.bot,
                    category_key=self.category_key,
                    subject=subject,
                    description=description,
                )
                await confirm_interaction.followup.send(
                    f"✅ 問い合わせを受け付けたで！\n{channel.mention} で続けてな 🎫",
                    ephemeral=True,
                )
            except ValueError as exc:
                reason = str(exc)
                if reason.startswith("open_ticket_exists:"):
                    channel_id = reason.split(":", 1)[1]
                    await confirm_interaction.followup.send(
                        f"📩 すでに開いてる問い合わせがあるで。\n<#{channel_id}>",
                        ephemeral=True,
                    )
                else:
                    await confirm_interaction.followup.send(
                        "Ticketを作れへんかったで。サーバー内でもう一度試してな。",
                        ephemeral=True,
                    )
            except discord.Forbidden:
                await confirm_interaction.followup.send(
                    "チャンネルを作る権限が茜に足りへんみたいや。管理者に確認してな。",
                    ephemeral=True,
                )
            except Exception as exc:
                logger.exception("Native ticket create failed: %s", exc)
                await confirm_interaction.followup.send(
                    "Ticket作成中にエラーが起きたで。変更は途中で止めてあるで。",
                    ephemeral=True,
                )

        preview = (
            f"{emoji} **{label}**\n"
            f"**件名:** {subject}\n"
            f"**内容:** {description}\n\n"
            "この内容で管理人・運営に問い合わせる？\n"
            "確定するまではTicketは作られへんで👌"
        )
        await interaction.response.send_message(
            preview,
            view=ConfirmActionView(
                requester_id=self.requester_id,
                on_confirm=execute,
                confirm_label="問い合わせを送る",
            ),
            ephemeral=True,
        )


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot) -> None:
        self.bot = bot
        super().__init__(
            placeholder="問い合わせの種類を選んでな",
            min_values=1,
            max_values=1,
            custom_id="ticket_category_select",
            options=[
                discord.SelectOption(label="管理者への相談", emoji="🛡️", value="admin"),
                discord.SelectOption(label="Botの不具合", emoji="🤖", value="bot"),
                discord.SelectOption(label="サーバーについて", emoji="💬", value="server"),
                discord.SelectOption(label="その他", emoji="📦", value="other"),
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("この機能はサーバー内専用やで。", ephemeral=True)
            return
        existing = await _store(self.bot).get_open_for_user(
            interaction.guild.id,
            interaction.user.id,
        )
        if existing is not None and interaction.guild.get_channel(existing.channel_id):
            await interaction.response.send_message(
                f"📩 すでに開いてる問い合わせがあるで！\n<#{existing.channel_id}>",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            TicketCreateModal(
                bot=self.bot,
                requester_id=interaction.user.id,
                category_key=self.values[0],
            )
        )


class TicketView(discord.ui.View):
    """Persistent public Ticket entry panel (legacy custom ID preserved)."""

    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TicketCategorySelect(bot))


class TicketCreateEntryView(RequesterOnlyView):
    """Natural-language entry point; no third-party Ticket Tool hand-off."""

    def __init__(self, *, bot, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        select = TicketCategorySelect(bot)
        # A select's own callback performs requester validation here because the
        # child callback may be invoked independently of View.interaction_check in tests.
        self.add_item(select)
        cancel = discord.ui.Button(
            label="キャンセル",
            style=discord.ButtonStyle.secondary,
            custom_id="ticket_create:cancel",
        )

        async def cancel_cb(interaction: discord.Interaction) -> None:
            self.cancelled = True
            self.disable_all()
            self.stop()
            await interaction.response.edit_message(
                content="キャンセルしたで👌 問い合わせは送ってへんで。",
                view=self,
            )

        cancel.callback = cancel_cb
        self.add_item(cancel)


async def _ticket_for_interaction(interaction: discord.Interaction, bot) -> NativeTicketRecord | None:
    if interaction.channel_id is None:
        return None
    return await _store(bot).get_by_channel(interaction.channel_id)


async def _can_close(interaction: discord.Interaction, bot, ticket: NativeTicketRecord) -> bool:
    return interaction.user.id == ticket.user_id or await is_ticket_staff(interaction, bot)


class TicketOpenView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="閉じる",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_button",
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        ticket = await _ticket_for_interaction(interaction, self.bot)
        if ticket is None or ticket.status != "open":
            await interaction.response.send_message("このTicketは開いてへんみたいや。", ephemeral=True)
            return
        if not await _can_close(interaction, self.bot, ticket):
            await interaction.response.send_message(
                "このTicketを閉じられるんは作成者かTicket担当者だけやで。",
                ephemeral=True,
            )
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await _close_ticket(confirm_interaction, self.bot, ticket)

        await interaction.response.send_message(
            "🔒 このTicketを閉じる？\n閉じてもチャンネルはすぐ削除せず、担当者が再開できるで。",
            view=ConfirmActionView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label="Ticketを閉じる",
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="担当する",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim_button",
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(interaction, self.bot):
            return
        ticket = await _ticket_for_interaction(interaction, self.bot)
        if ticket is None or ticket.status != "open":
            await interaction.response.send_message("開いてるTicket情報が見つからへんで。", ephemeral=True)
            return
        await _store(self.bot).claim(ticket.id, interaction.user.id)
        await _store(self.bot).audit(ticket.id, interaction.user.id, "claim")
        await interaction.response.send_message(
            f"🙋 {interaction.user.mention} がこのTicketを担当するで。",
        )

    @discord.ui.button(
        label="管理",
        emoji="⚙️",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_manage_button",
    )
    async def manage(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(interaction, self.bot):
            return
        await interaction.response.send_message(
            "⚙️ Ticket管理やで。操作を選んでな。",
            view=TicketManageView(self.bot, interaction.user.id),
            ephemeral=True,
        )


# Backward-compatible public class name used by app.py and old persistent panels.
TicketCloseView = TicketOpenView


async def _close_ticket(interaction: discord.Interaction, bot, ticket: NativeTicketRecord) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Ticketチャンネルで使ってな。", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    store = _store(bot)
    try:
        transcript_bytes = await create_transcript(channel)
        log_id = await bot.db.get_config(channel.guild.id, "log_ch")
        log_channel = channel.guild.get_channel(log_id) if log_id else None
        if log_channel is not None:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"📁 Ticket #{(ticket.ticket_number or ticket.id):04d} Closed",
                    description=f"閉じた人: {interaction.user.mention}\n作成者: <@{ticket.user_id}>",
                    color=discord.Color.orange(),
                ),
                file=discord.File(
                    io.BytesIO(transcript_bytes),
                    filename=f"ticket-{ticket.ticket_number or ticket.id:04d}-transcript.txt",
                ),
            )
        member = channel.guild.get_member(ticket.user_id)
        if member is not None:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=False,
                read_message_history=True,
            )
        await store.set_status(ticket.id, "closed")
        await store.audit(ticket.id, interaction.user.id, "close")
        number = ticket.ticket_number or ticket.id
        await channel.edit(name=_ticket_channel_name(number, closed=True), reason="Akane Ticket closed")
        await channel.send(
            "🔒 Ticketを閉じたで。担当者は下のボタンから再開・削除できるで。",
            view=TicketClosedView(bot),
        )
        await interaction.followup.send("✅ Ticketを閉じたで。チャンネルは保管してあるで。", ephemeral=True)
    except Exception as exc:
        logger.exception("Native ticket close failed: %s", exc)
        await interaction.followup.send("Ticketを閉じる処理中にエラーが起きたで。", ephemeral=True)


class RenameTicketModal(discord.ui.Modal, title="Ticket件名を変更"):
    subject = discord.ui.TextInput(label="新しい件名", min_length=1, max_length=100)

    def __init__(self, *, bot, requester_id: int) -> None:
        super().__init__()
        self.bot = bot
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("この操作を始めた本人だけ使えるで。", ephemeral=True)
            return
        ticket = await _ticket_for_interaction(interaction, self.bot)
        if ticket is None:
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        subject = str(self.subject.value).strip()
        await _store(self.bot).rename_subject(ticket.id, subject)
        await _store(self.bot).audit(ticket.id, interaction.user.id, "rename", subject)
        await interaction.response.send_message(f"✏️ 件名を **{subject}** に変更したで。", ephemeral=True)


class TicketMemberSelect(discord.ui.UserSelect):
    def __init__(self, *, bot, requester_id: int, remove: bool) -> None:
        self.bot = bot
        self.requester_id = requester_id
        self.remove = remove
        super().__init__(
            placeholder="メンバーを選んでな",
            min_values=1,
            max_values=1,
            custom_id=f"ticket_member:{'remove' if remove else 'add'}",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.requester_id or not await is_ticket_staff(interaction, self.bot):
            await interaction.response.send_message("Ticket担当者だけ使える操作やで。", ephemeral=True)
            return
        ticket = await _ticket_for_interaction(interaction, self.bot)
        member = self.values[0]
        channel = interaction.channel
        if ticket is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        if self.remove:
            if member.id == ticket.user_id:
                await interaction.response.send_message("Ticket作成者はここでは外せへんで。", ephemeral=True)
                return
            await channel.set_permissions(member, overwrite=None, reason="Akane Ticket member removed")
            await _store(self.bot).remove_member(ticket.id, member.id)
            action = "remove_member"
            text = f"➖ {member.mention} をTicketから外したで。"
        else:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                reason="Akane Ticket member added",
            )
            await _store(self.bot).add_member(ticket.id, member.id)
            action = "add_member"
            text = f"➕ {member.mention} をTicketに追加したで。"
        await _store(self.bot).audit(ticket.id, interaction.user.id, action, str(member.id))
        await interaction.response.send_message(text)


class TicketMemberSelectView(RequesterOnlyView):
    def __init__(self, *, bot, requester_id: int, remove: bool) -> None:
        super().__init__(requester_id=requester_id)
        self.add_item(TicketMemberSelect(bot=bot, requester_id=requester_id, remove=remove))


class TicketManageView(RequesterOnlyView):
    def __init__(self, bot, requester_id: int) -> None:
        super().__init__(requester_id=requester_id)
        self.bot = bot

        rename = discord.ui.Button(label="件名変更", emoji="✏️", style=discord.ButtonStyle.secondary)
        add = discord.ui.Button(label="メンバー追加", emoji="➕", style=discord.ButtonStyle.secondary)
        remove = discord.ui.Button(label="メンバー削除", emoji="➖", style=discord.ButtonStyle.secondary)

        async def rename_cb(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                RenameTicketModal(bot=self.bot, requester_id=self.requester_id)
            )

        async def add_cb(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(
                content="➕ Ticketに追加するメンバーを選んでな。",
                view=TicketMemberSelectView(bot=self.bot, requester_id=self.requester_id, remove=False),
            )

        async def remove_cb(interaction: discord.Interaction) -> None:
            await interaction.response.edit_message(
                content="➖ Ticketから外すメンバーを選んでな。",
                view=TicketMemberSelectView(bot=self.bot, requester_id=self.requester_id, remove=True),
            )

        rename.callback = rename_cb
        add.callback = add_cb
        remove.callback = remove_cb
        self.add_item(rename)
        self.add_item(add)
        self.add_item(remove)


class TicketClosedView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="再開",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen_button",
    )
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(interaction, self.bot):
            return
        ticket = await _ticket_for_interaction(interaction, self.bot)
        channel = interaction.channel
        if ticket is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return
        if ticket.status != "closed":
            await interaction.response.send_message("このTicketは閉じられてへんで。", ephemeral=True)
            return
        member = channel.guild.get_member(ticket.user_id)
        if member is not None:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            )
        await _store(self.bot).set_status(ticket.id, "open")
        await _store(self.bot).audit(ticket.id, interaction.user.id, "reopen")
        number = ticket.ticket_number or ticket.id
        await channel.edit(name=_ticket_channel_name(number), reason="Akane Ticket reopened")
        await interaction.response.send_message(
            "🔓 Ticketを再開したで。",
            view=TicketOpenView(self.bot),
        )

    @discord.ui.button(
        label="完全削除",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete_button",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _require_staff(interaction, self.bot):
            return
        ticket = await _ticket_for_interaction(interaction, self.bot)
        if ticket is None:
            await interaction.response.send_message("Ticket情報が見つからへんで。", ephemeral=True)
            return

        async def execute(confirm_interaction: discord.Interaction) -> None:
            await confirm_interaction.response.defer(ephemeral=True)
            await _store(self.bot).set_status(ticket.id, "deleted")
            await _store(self.bot).audit(ticket.id, confirm_interaction.user.id, "delete")
            await confirm_interaction.followup.send("🗑️ Ticketを完全削除するで。", ephemeral=True)
            await confirm_interaction.channel.delete(reason="Akane Ticket deleted by staff")

        await interaction.response.send_message(
            "⚠️ このTicketチャンネルを完全に削除する？\nこの操作は元に戻せへんで。",
            view=ConfirmActionView(
                requester_id=interaction.user.id,
                on_confirm=execute,
                confirm_label="完全削除する",
            ),
            ephemeral=True,
        )
