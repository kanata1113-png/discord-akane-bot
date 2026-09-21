from __future__ import annotations

from datetime import datetime

from config import JST
from repositories.base import BaseRepository


class TicketRepository(BaseRepository):
    async def get_open_for_user(self, guild_id: int, user_id: int):
        return await self.store.fetchone(
            """
            SELECT id, channel_id, category, created_at
            FROM tickets
            WHERE guild_id=? AND user_id=? AND status='open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id, user_id),
        )

    async def get_by_channel(self, channel_id: int):
        return await self.store.fetchone(
            """
            SELECT id, guild_id, channel_id, user_id, category,
                   status, created_at, closed_at
            FROM tickets
            WHERE channel_id=?
            """,
            (channel_id,),
        )

    async def get_native_by_channel(self, channel_id: int):
        return await self.store.fetchone(
            """
            SELECT id, guild_id, channel_id, user_id, category,
                   status, created_at, closed_at, ticket_number,
                   subject, claimed_by, deleted_at
            FROM tickets
            WHERE channel_id=?
            """,
            (channel_id,),
        )

    async def reserve_number(self, guild_id: int) -> int:
        """Atomically reserve the next human-facing ticket number per guild."""
        async with self.store.transaction() as db:
            cursor = await db.execute(
                "SELECT next_number FROM ticket_counters WHERE guild_id=?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                number = 1
                await db.execute(
                    "INSERT INTO ticket_counters (guild_id, next_number) VALUES (?, ?)",
                    (guild_id, 2),
                )
            else:
                number = int(row[0])
                await db.execute(
                    "UPDATE ticket_counters SET next_number=? WHERE guild_id=?",
                    (number + 1, guild_id),
                )
            return number

    async def create(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
        *,
        ticket_number: int | None = None,
        subject: str | None = None,
    ) -> int:
        created_at = datetime.now(JST).isoformat()
        # Preserve the pre-v2 repository contract for characterization tests and
        # staged callers that do not use native-ticket metadata yet.
        if ticket_number is None and subject is None:
            return await self.store.insert(
                """
                INSERT INTO tickets
                (guild_id, channel_id, user_id, category, status, created_at)
                VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (guild_id, channel_id, user_id, category, created_at),
            )
        return await self.store.insert(
            """
            INSERT INTO tickets
            (guild_id, channel_id, user_id, category, status, created_at,
             ticket_number, subject)
            VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (guild_id, channel_id, user_id, category, created_at, ticket_number, subject),
        )

    async def close(self, channel_id: int) -> None:
        await self.store.execute(
            """
            UPDATE tickets
            SET status='closed', closed_at=?
            WHERE channel_id=? AND status='open'
            """,
            (datetime.now(JST).isoformat(), channel_id),
        )

    async def reopen(self, channel_id: int) -> None:
        await self.store.execute(
            """
            UPDATE tickets
            SET status='open', closed_at=NULL
            WHERE channel_id=? AND status='closed'
            """,
            (channel_id,),
        )

    async def claim(self, channel_id: int, user_id: int | None) -> None:
        await self.store.execute(
            "UPDATE tickets SET claimed_by=? WHERE channel_id=?",
            (user_id, channel_id),
        )

    async def mark_deleted(self, channel_id: int) -> None:
        await self.store.execute(
            """
            UPDATE tickets
            SET status='deleted', deleted_at=?
            WHERE channel_id=?
            """,
            (datetime.now(JST).isoformat(), channel_id),
        )

    async def delete_by_channel(self, channel_id: int) -> None:
        await self.store.execute("DELETE FROM tickets WHERE channel_id=?", (channel_id,))

    async def get_settings(self, guild_id: int):
        return await self.store.fetchone(
            "SELECT category_id, staff_role_id FROM ticket_settings WHERE guild_id=?",
            (guild_id,),
        )

    async def set_category(self, guild_id: int, category_id: int | None) -> None:
        now = datetime.now(JST).isoformat()
        await self.store.execute(
            """
            INSERT INTO ticket_settings (guild_id, category_id, staff_role_id, updated_at)
            VALUES (?, ?, NULL, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                category_id=excluded.category_id,
                updated_at=excluded.updated_at
            """,
            (guild_id, category_id, now),
        )

    async def set_staff_role(self, guild_id: int, role_id: int | None) -> None:
        now = datetime.now(JST).isoformat()
        await self.store.execute(
            """
            INSERT INTO ticket_settings (guild_id, category_id, staff_role_id, updated_at)
            VALUES (?, NULL, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                staff_role_id=excluded.staff_role_id,
                updated_at=excluded.updated_at
            """,
            (guild_id, role_id, now),
        )

    async def add_member(self, ticket_id: int, user_id: int) -> None:
        await self.store.execute(
            """
            INSERT OR IGNORE INTO ticket_members (ticket_id, user_id, added_at)
            VALUES (?, ?, ?)
            """,
            (ticket_id, user_id, datetime.now(JST).isoformat()),
        )

    async def remove_member(self, ticket_id: int, user_id: int) -> None:
        await self.store.execute(
            "DELETE FROM ticket_members WHERE ticket_id=? AND user_id=?",
            (ticket_id, user_id),
        )

    async def list_members(self, ticket_id: int):
        return await self.store.fetchall(
            "SELECT user_id FROM ticket_members WHERE ticket_id=? ORDER BY added_at ASC",
            (ticket_id,),
        )

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
        await self.store.insert(
            """
            INSERT INTO ticket_audit
            (ticket_id, guild_id, channel_id, actor_id, action, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, guild_id, channel_id, actor_id, action, detail, datetime.now(JST).isoformat()),
        )
