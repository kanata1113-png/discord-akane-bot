import pytest

from database import DatabaseManager


EXPECTED_ACHIEVEMENTS = {
    "first_message",
    "messages_100",
    "messages_500",
    "messages_1000",
    "level_5",
    "level_10",
    "level_20",
    "ai_10",
    "ai_100",
    "fortune_1",
    "fortune_10",
    "ticket_1",
}

EXPECTED_TITLES = {
    "newcomer",
    "regular",
    "talkative",
    "veteran",
    "level5",
    "level10",
    "level20",
    "ai_friend",
    "ai_partner",
    "supporter",
    "lucky",
}


@pytest.mark.asyncio
async def test_current_progress_thresholds_unlock_expected_items(tmp_path):
    manager = DatabaseManager(str(tmp_path / "akane.db"))
    await manager.init()

    guild_id = 100
    user_id = 200

    await manager._execute(
        "INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)",
        (user_id, 0, 20),
    )
    await manager._execute(
        """
        INSERT INTO user_stats (
            guild_id, user_id, message_count, ai_chat_count,
            fortune_count, ticket_count, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (guild_id, user_id, 1000, 100, 10, 1, "now", "now"),
    )

    unlocked = await manager.evaluate_progress_unlocks(guild_id, user_id)

    assert set(unlocked["achievements"]) == EXPECTED_ACHIEVEMENTS
    assert set(unlocked["titles"]) == EXPECTED_TITLES

    second_pass = await manager.evaluate_progress_unlocks(guild_id, user_id)
    assert second_pass == {"achievements": [], "titles": []}


@pytest.mark.asyncio
async def test_first_message_unlocks_only_entry_level_progress(tmp_path):
    manager = DatabaseManager(str(tmp_path / "akane.db"))
    await manager.init()

    guild_id = 101
    user_id = 201

    await manager._execute(
        """
        INSERT INTO user_stats (
            guild_id, user_id, message_count, ai_chat_count,
            fortune_count, ticket_count, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (guild_id, user_id, 1, 0, 0, 0, "now", "now"),
    )

    unlocked = await manager.evaluate_progress_unlocks(guild_id, user_id)

    assert unlocked["achievements"] == ["first_message"]
    assert unlocked["titles"] == ["newcomer"]
