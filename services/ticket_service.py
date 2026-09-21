from __future__ import annotations

from repositories.ticket_repository import TicketRepository


class TicketService:
    def __init__(self, tickets: TicketRepository):
        self.tickets = tickets

    async def get_open_ticket(self, guild_id: int, user_id: int):
        return await self.tickets.get_open_for_user(guild_id, user_id)

    async def get_ticket_by_channel(self, channel_id: int):
        row = await self.tickets.get_by_channel(channel_id)
        if not row:
            return None

        (
            ticket_id,
            guild_id,
            _channel_id,
            user_id,
            category,
            status,
            created_at,
            closed_at,
        ) = row
        return (
            ticket_id,
            guild_id,
            user_id,
            category,
            status,
            created_at,
            closed_at,
        )

    async def get_native_ticket(self, channel_id: int):
        row = await self.tickets.get_native_by_channel(channel_id)
        if not row:
            return None
        keys = (
            "id",
            "guild_id",
            "channel_id",
            "user_id",
            "category",
            "status",
            "created_at",
            "closed_at",
            "ticket_number",
            "subject",
            "claimed_by",
            "deleted_at",
        )
        return dict(zip(keys, row))

    async def reserve_ticket_number(self, guild_id: int) -> int:
        return await self.tickets.reserve_number(guild_id)

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
        *,
        ticket_number: int | None = None,
        subject: str | None = None,
    ) -> int:
        existing = await self.get_open_ticket(guild_id, user_id)
        if existing:
            raise ValueError("User already has an open ticket.")

        return await self.tickets.create(
            guild_id,
            channel_id,
            user_id,
            category,
            ticket_number=ticket_number,
            subject=subject,
        )

    async def close_ticket(self, channel_id: int) -> None:
        await self.tickets.close(channel_id)

    async def reopen_ticket(self, channel_id: int) -> None:
        await self.tickets.reopen(channel_id)

    async def claim_ticket(self, channel_id: int, user_id: int | None) -> None:
        await self.tickets.claim(channel_id, user_id)

    async def mark_ticket_deleted(self, channel_id: int) -> None:
        await self.tickets.mark_deleted(channel_id)

    async def cleanup_missing_ticket(self, channel_id: int) -> None:
        await self.close_ticket(channel_id)

    async def count_open_tickets(self, guild_id: int) -> int:
        row = await self.tickets.store.fetchone(
            """
            SELECT COUNT(*)
            FROM tickets
            WHERE guild_id=? AND status='open'
            """,
            (guild_id,),
        )
        return int(row[0]) if row else 0

    async def get_ticket_settings(self, guild_id: int) -> dict[str, int | None]:
        row = await self.tickets.get_settings(guild_id)
        if not row:
            return {"category_id": None, "staff_role_id": None}
        return {"category_id": row[0], "staff_role_id": row[1]}

    async def set_ticket_category(self, guild_id: int, category_id: int | None) -> None:
        await self.tickets.set_category(guild_id, category_id)

    async def set_staff_role(self, guild_id: int, role_id: int | None) -> None:
        await self.tickets.set_staff_role(guild_id, role_id)

    async def add_ticket_member(self, ticket_id: int, user_id: int) -> None:
        await self.tickets.add_member(ticket_id, user_id)

    async def remove_ticket_member(self, ticket_id: int, user_id: int) -> None:
        await self.tickets.remove_member(ticket_id, user_id)

    async def list_ticket_members(self, ticket_id: int) -> tuple[int, ...]:
        rows = await self.tickets.list_members(ticket_id)
        return tuple(int(row[0]) for row in rows)

    async def audit(
        self,
        *,
        ticket_id: int | None,
        guild_id: int,
        channel_id: int | None,
        actor_id: int | None,
        action: str,
        detail: str | None = None,
    ) -> None:
        await self.tickets.audit(
            ticket_id=ticket_id,
            guild_id=guild_id,
            channel_id=channel_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
        )
