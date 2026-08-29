from __future__ import annotations

from repositories.base import BaseRepository


class GuildRepository(BaseRepository):
    ALLOWED_CONFIG_COLUMNS = {
        "welcome_ch",
        "log_ch",
        "starboard_ch",
        "auto_chat_ch",
    }

    async def set_config(self, guild_id: int, column: str, value: int) -> None:
        if column not in self.ALLOWED_CONFIG_COLUMNS:
            raise ValueError(f"Invalid guild config column: {column}")

        await self.store.execute(
            f"""
            INSERT INTO guild_settings (guild_id, {column})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {column}=excluded.{column}
            """,
            (guild_id, value),
        )

    async def get_config(self, guild_id: int, column: str):
        if column not in self.ALLOWED_CONFIG_COLUMNS:
            raise ValueError(f"Invalid guild config column: {column}")

        row = await self.store.fetchone(
            f"SELECT {column} FROM guild_settings WHERE guild_id=?",
            (guild_id,),
        )
        return row[0] if row else None
