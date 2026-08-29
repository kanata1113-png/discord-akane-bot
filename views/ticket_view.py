import asyncio
import io
import logging

from datetime import datetime

import discord

from config import Config, JST


logger = logging.getLogger(
    "AkaneBot"
)


# ==============================================================================
# Helper
# ==============================================================================

def safe_channel_name(
    text: str
) -> str:

    result = ""

    for char in text.lower():

        if (
            char.isalnum()
            or char in {
                "-",
                "_",
            }
        ):

            result += char

    result = result.strip(
        "-_"
    )

    if not result:

        result = "user"

    return result[:30]


# ==============================================================================
# Transcript
# ==============================================================================

async def create_transcript(
    channel: discord.TextChannel
) -> bytes:

    lines = []

    lines.append(
        "========================================"
    )

    lines.append(
        "Akane Bot Ticket Transcript"
    )

    lines.append(
        f"Guild: {channel.guild.name}"
    )

    lines.append(
        f"Channel: #{channel.name}"
    )

    lines.append(
        f"Channel ID: {channel.id}"
    )

    lines.append(
        "Generated: "
        f"{datetime.now(JST).isoformat()}"
    )

    lines.append(
        "========================================"
    )

    lines.append(
        ""
    )

    try:

        async for message in channel.history(
            limit=(
                Config
                .TICKET_TRANSCRIPT_LIMIT
            ),
            oldest_first=True
        ):

            created = (
                message.created_at
                .astimezone(
                    JST
                )
                .strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            author = (
                f"{message.author} "
                f"({message.author.id})"
            )

            content = (
                message.content
                or ""
            )

            lines.append(
                f"[{created}] "
                f"{author}"
            )

            if content:

                lines.append(
                    content
                )

            for attachment in (
                message.attachments
            ):

                lines.append(
                    "[Attachment] "
                    f"{attachment.url}"
                )

            if message.embeds:

                lines.append(
                    "[Embeds] "
                    f"{len(message.embeds)}"
                )

            lines.append(
                ""
            )

    except Exception as e:

        logger.exception(
            "Transcript generation "
            f"failed: {e}"
        )

        lines.append(
            ""
        )

        lines.append(
            "[ERROR] "
            "Transcriptの一部取得に"
            "失敗しました。"
        )

    transcript = "\n".join(
        lines
    )

    return transcript.encode(
        "utf-8"
    )


# ==============================================================================
# V32 Ticket Unlock Notification
# ==============================================================================

async def send_ticket_unlock_notifications(
    channel,
    member,
    unlocks: dict
):

    if not Config.ACHIEVEMENT_NOTIFICATIONS:

        return

    achievement_keys = unlocks.get(
        "achievements",
        []
    )

    title_keys = unlocks.get(
        "titles",
        []
    )

    if (
        not achievement_keys
        and not title_keys
    ):

        return

    lines = []

    for key in achievement_keys:

        data = (
            Config.ACHIEVEMENTS.get(
                key
            )
        )

        if not data:

            continue

        lines.append(
            f"🏆 実績解除: "
            f"{data['emoji']} "
            f"**{data['name']}**"
        )

    for key in title_keys:

        data = (
            Config.TITLES.get(
                key
            )
        )

        if not data:

            continue

        lines.append(
            f"🎖️ 称号獲得: "
            f"**{data['name']}**"
        )

    if not lines:

        return

    try:

        embed = discord.Embed(
            title="🎉 新しい解除項目",
            description="\n".join(
                lines
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="Akane Bot v32"
        )

        await channel.send(
            content=member.mention,
            embed=embed
        )

    except Exception as e:

        logger.exception(
            "Ticket unlock notification "
            f"failed: {e}"
        )


# ==============================================================================
# Ticket Category Select
# ==============================================================================

class TicketCategorySelect(
    discord.ui.Select
):

    def __init__(
        self,
        bot
    ):

        self.bot = bot

        options = [
            discord.SelectOption(
                label="管理者への相談",
                description=(
                    "管理者に相談したいことがある"
                ),
                emoji="🛡️",
                value="admin"
            ),

            discord.SelectOption(
                label="Botの不具合",
                description=(
                    "茜Botの不具合・エラーなど"
                ),
                emoji="🤖",
                value="bot"
            ),

            discord.SelectOption(
                label="サーバーについて",
                description=(
                    "サーバー運営やルールについて"
                ),
                emoji="💬",
                value="server"
            ),

            discord.SelectOption(
                label="その他",
                description=(
                    "上記に当てはまらない問い合わせ"
                ),
                emoji="📦",
                value="other"
            ),
        ]

        super().__init__(
            placeholder=(
                "問い合わせの種類を選んでな"
            ),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=(
                "ticket_category_select"
            )
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.guild:

            await interaction.response.send_message(
                "この機能は"
                "サーバー内専用やで。",
                ephemeral=True
            )

            return

        selected = (
            self.values[0]
        )

        category_map = {
            "admin": (
                "管理者への相談",
                "🛡️"
            ),

            "bot": (
                "Botの不具合",
                "🤖"
            ),

            "server": (
                "サーバーについて",
                "💬"
            ),

            "other": (
                "その他",
                "📦"
            ),
        }

        (
            category_name,
            emoji
        ) = category_map[
            selected
        ]

        # ======================================================================
        # Duplicate Ticket Check
        # ======================================================================

        try:

            existing = (
                await self.bot.db
                .get_open_ticket(
                    interaction.guild.id,
                    interaction.user.id
                )
            )

        except Exception as e:

            logger.exception(
                "Ticket duplicate check "
                f"failed: {e}"
            )

            await interaction.response.send_message(
                "Ticket情報の確認中に"
                "エラーが起きたで。",
                ephemeral=True
            )

            return

        if existing:

            existing_channel_id = (
                existing[1]
            )

            existing_channel = (
                interaction.guild
                .get_channel(
                    existing_channel_id
                )
            )

            # ------------------------------------------------------------------
            # DBではOpenだが
            # Discord側で削除済み
            # ------------------------------------------------------------------

            if not existing_channel:

                try:

                    await self.bot.db.close_ticket(
                        existing_channel_id
                    )

                except Exception as e:

                    logger.exception(
                        "Missing ticket cleanup "
                        f"failed: {e}"
                    )

            else:

                await interaction.response.send_message(
                    "📩 すでに開いてる"
                    "問い合わせがあるで！\n"
                    f"{existing_channel.mention}",
                    ephemeral=True
                )

                return

        # ======================================================================
        # Defer
        # ======================================================================

        await interaction.response.defer(
            ephemeral=True
        )

        channel = None

        try:

            bot_member = (
                interaction.guild.me
            )

            overwrites = {
                interaction.guild.default_role:
                    discord.PermissionOverwrite(
                        view_channel=False
                    ),

                interaction.user:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True
                    ),

                bot_member:
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_channels=True
                    ),
            }

            username = (
                safe_channel_name(
                    interaction.user.name
                )
            )

            channel_name = (
                f"ticket-"
                f"{username}-"
                f"{str(interaction.user.id)[-4:]}"
            )

            channel = (
                await interaction.guild
                .create_text_channel(
                    channel_name,
                    overwrites=overwrites,
                    reason=(
                        "Akane Bot Ticket"
                    )
                )
            )

            # ==================================================================
            # DB Ticket
            # ==================================================================

            await self.bot.db.create_ticket(
                guild_id=(
                    interaction.guild.id
                ),
                channel_id=(
                    channel.id
                ),
                user_id=(
                    interaction.user.id
                ),
                category=selected
            )

            # ==================================================================
            # Welcome Embed
            # ==================================================================

            embed = discord.Embed(
                title=(
                    f"{emoji} "
                    f"{category_name}"
                ),
                description=(
                    f"{interaction.user.mention} "
                    "問い合わせありがとうな！\n\n"
                    "ここに詳しい内容を書いてな。"
                    "管理者が確認できるように"
                    "してあるで。\n\n"
                    "解決したら下の"
                    "「解決・閉じる」ボタンを"
                    "押してな。"
                ),
                color=discord.Color.blue()
            )

            embed.add_field(
                name="問い合わせ種別",
                value=category_name,
                inline=True
            )

            embed.add_field(
                name="作成者",
                value=(
                    interaction.user.mention
                ),
                inline=True
            )

            embed.add_field(
                name="Ticket ID",
                value=(
                    f"`{channel.id}`"
                ),
                inline=False
            )

            embed.set_footer(
                text="Akane Bot v32 Ticket"
            )

            await channel.send(
                content=(
                    interaction.user.mention
                ),
                embed=embed,
                view=TicketCloseView(
                    self.bot
                )
            )

            # ==================================================================
            # V32 Ticket Statistics
            # ==================================================================

            try:

                ticket_count = (
                    await self.bot.db
                    .increment_ticket_count(
                        guild_id=(
                            interaction.guild.id
                        ),
                        user_id=(
                            interaction.user.id
                        )
                    )
                )

                logger.info(
                    "Ticket stat incremented | "
                    f"guild="
                    f"{interaction.guild.id} | "
                    f"user="
                    f"{interaction.user.id} | "
                    f"count="
                    f"{ticket_count}"
                )

                unlocks = (
                    await self.bot.db
                    .evaluate_progress_unlocks(
                        guild_id=(
                            interaction.guild.id
                        ),
                        user_id=(
                            interaction.user.id
                        )
                    )
                )

                await (
                    send_ticket_unlock_notifications(
                        channel,
                        interaction.user,
                        unlocks
                    )
                )

            except Exception as e:

                # Stats障害で
                # Ticket自体は消さない
                logger.exception(
                    "V32 ticket stats "
                    f"failed: {e}"
                )

            # ==================================================================
            # User Response
            # ==================================================================

            await interaction.followup.send(
                "✅ 問い合わせ用の"
                "チャンネルを作ったで！\n"
                f"{channel.mention}",
                ephemeral=True
            )

            logger.info(
                "Ticket created | "
                f"guild={interaction.guild.id} | "
                f"user={interaction.user.id} | "
                f"channel={channel.id} | "
                f"category={selected}"
            )

        except ValueError:

            # DB重複防止

            if channel:

                try:

                    await channel.delete(
                        reason=(
                            "Duplicate Ticket"
                        )
                    )

                except Exception:

                    pass

            await interaction.followup.send(
                "すでに開いてる"
                "問い合わせがあるみたいや。",
                ephemeral=True
            )

        except discord.Forbidden:

            logger.warning(
                "Ticket creation "
                "permission denied."
            )

            if channel:

                try:

                    await channel.delete()

                except Exception:

                    pass

            await interaction.followup.send(
                "チャンネルを作る"
                "権限が茜にないみたいや。",
                ephemeral=True
            )

        except Exception as e:

            logger.exception(
                "Ticket creation failed | "
                f"error={e}"
            )

            if channel:

                try:

                    await channel.delete()

                except Exception:

                    pass

            await interaction.followup.send(
                "Ticket作成中に"
                "エラーが起きたで。",
                ephemeral=True
            )


# ==============================================================================
# Main Ticket View
# ==============================================================================

class TicketView(
    discord.ui.View
):

    def __init__(
        self,
        bot
    ):

        super().__init__(
            timeout=None
        )

        self.bot = bot

        self.add_item(
            TicketCategorySelect(
                bot
            )
        )


# ==============================================================================
# Ticket Close View
# ==============================================================================

class TicketCloseView(
    discord.ui.View
):

    def __init__(
        self,
        bot
    ):

        super().__init__(
            timeout=None
        )

        self.bot = bot

    @discord.ui.button(
        label="解決・閉じる",
        style=(
            discord.ButtonStyle.danger
        ),
        emoji="🔒",
        custom_id=(
            "ticket_close_button"
        )
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        try:

            ticket = (
                await self.bot.db
                .get_ticket_by_channel(
                    interaction.channel.id
                )
            )

        except Exception as e:

            logger.exception(
                "Ticket lookup failed | "
                f"error={e}"
            )

            await interaction.response.send_message(
                "Ticket情報を"
                "確認できへんかったわ。",
                ephemeral=True
            )

            return

        if not ticket:

            await interaction.response.send_message(
                "このチャンネルは"
                "Ticketとして"
                "登録されてへんみたいや。",
                ephemeral=True
            )

            return

        ticket_user_id = (
            ticket[2]
        )

        is_owner = (
            interaction.user.id
            == ticket_user_id
        )

        is_admin = (
            interaction.user
            .guild_permissions
            .administrator
        )

        if not (
            is_owner
            or is_admin
        ):

            await interaction.response.send_message(
                "このTicketを閉じられるんは"
                "作成者か管理者だけやで。",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "⚠️ 本当にこの"
            "Ticketを閉じる？",
            view=TicketCloseConfirmView(
                self.bot,
                interaction.user.id
            ),
            ephemeral=True
        )


# ==============================================================================
# Ticket Close Confirmation
# ==============================================================================

class TicketCloseConfirmView(
    discord.ui.View
):

    def __init__(
        self,
        bot,
        requested_by: int
    ):

        super().__init__(
            timeout=(
                Config
                .TICKET_CLOSE_CONFIRM_TIMEOUT
            )
        )

        self.bot = bot

        self.requested_by = (
            requested_by
        )

        self.processing = False

    # ==========================================================================
    # Confirm
    # ==========================================================================

    @discord.ui.button(
        label="閉じる",
        style=(
            discord.ButtonStyle.danger
        ),
        emoji="✅"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if (
            interaction.user.id
            != self.requested_by
        ):

            await interaction.response.send_message(
                "この確認操作を"
                "できるんは"
                "実行した本人だけやで。",
                ephemeral=True
            )

            return

        if self.processing:

            await interaction.response.send_message(
                "いま処理中やで。",
                ephemeral=True
            )

            return

        self.processing = True

        await interaction.response.defer(
            ephemeral=True
        )

        channel = (
            interaction.channel
        )

        guild = (
            interaction.guild
        )

        try:

            ticket = (
                await self.bot.db
                .get_ticket_by_channel(
                    channel.id
                )
            )

            if not ticket:

                await interaction.followup.send(
                    "Ticket情報が"
                    "見つからへんかったわ。",
                    ephemeral=True
                )

                return

            (
                ticket_id,
                guild_id,
                ticket_user_id,
                category,
                status,
                created_at,
                closed_at
            ) = ticket

            if status != "open":

                await interaction.followup.send(
                    "このTicketは"
                    "すでに閉じられてるで。",
                    ephemeral=True
                )

                return

            # ==================================================================
            # Transcript
            # ==================================================================

            transcript_bytes = (
                await create_transcript(
                    channel
                )
            )

            transcript_filename = (
                f"ticket-"
                f"{channel.id}-"
                f"transcript.txt"
            )

            # ==================================================================
            # Log Channel
            # ==================================================================

            log_id = (
                await self.bot.db
                .get_config(
                    guild.id,
                    "log_ch"
                )
            )

            log_channel = (
                guild.get_channel(
                    log_id
                )
                if log_id
                else None
            )

            if log_channel:

                log_embed = discord.Embed(
                    title="📁 Ticket Closed",
                    color=(
                        discord.Color.orange()
                    ),
                    timestamp=(
                        datetime.now(
                            JST
                        )
                    )
                )

                log_embed.add_field(
                    name="Ticket",
                    value=(
                        f"`{ticket_id}`"
                    ),
                    inline=True
                )

                log_embed.add_field(
                    name="Channel",
                    value=(
                        f"`{channel.name}`"
                    ),
                    inline=True
                )

                log_embed.add_field(
                    name="作成者",
                    value=(
                        f"<@{ticket_user_id}>"
                    ),
                    inline=True
                )

                log_embed.add_field(
                    name="閉じた人",
                    value=(
                        interaction.user.mention
                    ),
                    inline=True
                )

                log_embed.add_field(
                    name="カテゴリ",
                    value=category,
                    inline=True
                )

                log_embed.add_field(
                    name="作成日時",
                    value=created_at,
                    inline=False
                )

                transcript_file = (
                    discord.File(
                        io.BytesIO(
                            transcript_bytes
                        ),
                        filename=(
                            transcript_filename
                        )
                    )
                )

                try:

                    await log_channel.send(
                        embed=log_embed,
                        file=transcript_file
                    )

                except Exception as e:

                    logger.exception(
                        "Ticket log send failed | "
                        f"error={e}"
                    )

            else:

                logger.warning(
                    "Ticket closed without "
                    "transcript log channel | "
                    f"guild={guild.id}"
                )

            # ==================================================================
            # DB Close
            # ==================================================================

            await self.bot.db.close_ticket(
                channel.id
            )

            # ==================================================================
            # Final Message
            # ==================================================================

            try:

                await channel.send(
                    "🔒 Ticketを閉じるで。\n"
                    "3秒後にこのチャンネルを"
                    "削除するな。"
                )

            except Exception:

                pass

            logger.info(
                "Ticket closed | "
                f"guild={guild.id} | "
                f"channel={channel.id} | "
                f"user={ticket_user_id} | "
                f"closed_by="
                f"{interaction.user.id}"
            )

            await asyncio.sleep(
                3
            )

            await channel.delete(
                reason=(
                    "Akane Bot Ticket Closed"
                )
            )

        except discord.Forbidden:

            logger.warning(
                "Ticket close "
                "permission denied."
            )

            try:

                await interaction.followup.send(
                    "Ticketを削除する"
                    "権限が茜にないみたいや。",
                    ephemeral=True
                )

            except Exception:

                pass

        except Exception as e:

            logger.exception(
                "Ticket close failed | "
                f"error={e}"
            )

            try:

                await interaction.followup.send(
                    "Ticketを閉じる処理中に"
                    "エラーが起きたで。",
                    ephemeral=True
                )

            except Exception:

                pass

        finally:

            self.processing = False

    # ==========================================================================
    # Cancel
    # ==========================================================================

    @discord.ui.button(
        label="キャンセル",
        style=(
            discord.ButtonStyle.secondary
        ),
        emoji="❌"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if (
            interaction.user.id
            != self.requested_by
        ):

            await interaction.response.send_message(
                "この確認操作を"
                "できるんは"
                "実行した本人だけやで。",
                ephemeral=True
            )

            return

        await interaction.response.edit_message(
            content=(
                "Ticketを閉じるのを"
                "キャンセルしたで。"
            ),
            view=None
        )

        self.stop()
