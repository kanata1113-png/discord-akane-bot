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

    async def create_ticket(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
    ) -> None:
        existing = await self.get_open_ticket(guild_id, user_id)
        if existing:
            raise ValueError("User already has an open ticket.")

        await self.tickets.create(
            guild_id,
            channel_id,
            user_id,
            category,
        )

    async def close_ticket(self, channel_id: int) -> None:
        await self.tickets.close(channel_id)

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
