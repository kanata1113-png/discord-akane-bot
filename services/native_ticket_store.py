from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from config import JST


@dataclass(frozen=True, slots=True)
class NativeTicketRecord:
    id: int
    guild_id: int
    channel_id: int
    user_id: int
    category: str
    status: str
    created_at: str
    closed_at: str | None
    ticket_number: int | None
    subject: str | None
    description: str | None
    assigned_staff_id: int | None
    updated_at: str | None


class NativeTicketStore:
    """Small additive persistence layer for the dogfood Ticket workflow."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @staticmethod
    def _now() -> str:
        return datetime.now(JST).isoformat()

    async def settings(self, guild_id: int) -> tuple[int | None, int | None]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT category_id, staff_role_id FROM ticket_settings WHERE guild_id=?",
                (guild_id,),
            )
            row = await cursor.fetchone()
            return (int(row[0]) if row and row[0] else None, int(row[1]) if row and row[1] else None)

    async def set_settings(
        self,
        guild_id: int,
        *,
        category_id: int | None,
        staff_role_id: int | None,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO ticket_settings (guild_id, category_id, staff_role_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    category_id=excluded.category_id,
                    staff_role_id=excluded.staff_role_id,
                    updated_at=excluded.updated_at
                """,
                (guild_id, category_id, staff_role_id, self._now()),
            )
            await db.commit()

    async def allocate_number(self, guild_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
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
                await db.commit()
                return number
            except Exception:
                await db.rollback()
                raise

    async def get_open_for_user(self, guild_id: int, user_id: int) -> NativeTicketRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, user_id, category, status,
                       created_at, closed_at, ticket_number, subject, description,
                       assigned_staff_id, updated_at
                FROM tickets
                WHERE guild_id=? AND user_id=? AND status='open'
                ORDER BY id DESC LIMIT 1
                """,
                (guild_id, user_id),
            )
            return self._record(await cursor.fetchone())

    async def get_by_channel(self, channel_id: int) -> NativeTicketRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT id, guild_id, channel_id, user_id, category, status,
                       created_at, closed_at, ticket_number, subject, description,
                       assigned_staff_id, updated_at
                FROM tickets WHERE channel_id=? ORDER BY id DESC LIMIT 1
                """,
                (channel_id,),
            )
            return self._record(await cursor.fetchone())

    @staticmethod
    def _record(row) -> NativeTicketRecord | None:
        if row is None:
            return None
        return NativeTicketRecord(
            id=int(row[0]), guild_id=int(row[1]), channel_id=int(row[2]),
            user_id=int(row[3]), category=str(row[4]), status=str(row[5]),
            created_at=str(row[6]), closed_at=str(row[7]) if row[7] else None,
            ticket_number=int(row[8]) if row[8] is not None else None,
            subject=str(row[9]) if row[9] else None,
            description=str(row[10]) if row[10] else None,
            assigned_staff_id=int(row[11]) if row[11] is not None else None,
            updated_at=str(row[12]) if row[12] else None,
        )

    async def create(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        category: str,
        ticket_number: int,
        subject: str,
        description: str,
    ) -> int:
        now = self._now()
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    "SELECT id FROM tickets WHERE guild_id=? AND user_id=? AND status='open' LIMIT 1",
                    (guild_id, user_id),
                )
                if await cursor.fetchone() is not None:
                    raise ValueError("open_ticket_exists")
                cursor = await db.execute(
                    """
                    INSERT INTO tickets (
                        guild_id, channel_id, user_id, category, status, created_at,
                        ticket_number, subject, description, updated_at
                    ) VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id, channel_id, user_id, category, now,
                        ticket_number, subject, description, now,
                    ),
                )
                ticket_id = int(cursor.lastrowid)
                await db.commit()
                return ticket_id
            except Exception:
                await db.rollback()
                raise

    async def set_status(self, ticket_id: int, status: str) -> None:
        now = self._now()
        closed_at = now if status == "closed" else None
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tickets SET status=?, closed_at=?, updated_at=? WHERE id=?",
                (status, closed_at, now, ticket_id),
            )
            await db.commit()

    async def claim(self, ticket_id: int, staff_id: int | None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tickets SET assigned_staff_id=?, updated_at=? WHERE id=?",
                (staff_id, self._now(), ticket_id),
            )
            await db.commit()

    async def rename_subject(self, ticket_id: int, subject: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tickets SET subject=?, updated_at=? WHERE id=?",
                (subject, self._now(), ticket_id),
            )
            await db.commit()

    async def add_member(self, ticket_id: int, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO ticket_members (ticket_id, user_id, added_at) VALUES (?, ?, ?)",
                (ticket_id, user_id, self._now()),
            )
            await db.commit()

    async def remove_member(self, ticket_id: int, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM ticket_members WHERE ticket_id=? AND user_id=?",
                (ticket_id, user_id),
            )
            await db.commit()

    async def audit(self, ticket_id: int, actor_id: int, action: str, detail: str | None = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO ticket_audit (ticket_id, actor_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                (ticket_id, actor_id, action, detail, self._now()),
            )
            await db.commit()
