from config import Config


def test_ai_model_routing_configuration_is_stable():
    assert Config.CHAT_MODEL == "gpt-5.6-terra"
    assert Config.REASONING_MODEL == "gpt-5.6-sol"
    assert Config.FAST_MODEL == "gpt-5.6-luna"
    assert Config.GPT_MODEL == Config.CHAT_MODEL

    assert Config.FAST_REASONING_EFFORT == "low"
    assert Config.CHAT_REASONING_EFFORT == "low"
    assert Config.REASONING_EFFORT == "medium"
    assert Config.DEEP_REASONING_EFFORT == "medium"


def test_core_limits_are_stable():
    assert Config.NORMAL_CHAT_MAX_TOKENS == 1500
    assert Config.DAILY_LIMIT == 100
    assert Config.MEMORY_MESSAGE_LIMIT == 12
    assert Config.MEMORY_RETENTION_DAYS == 30
    assert Config.XP_PER_MESSAGE == 10
    assert Config.XP_COOLDOWN_SECONDS == 60


def test_spam_thresholds_are_stable():
    assert Config.SPAM_WINDOW_SECONDS == 5
    assert Config.SPAM_MESSAGE_THRESHOLD == 5
    assert Config.SPAM_STRIKE_RESET_SECONDS == 1800
    assert Config.SPAM_TIMEOUT_1_SECONDS == 30
    assert Config.SPAM_TIMEOUT_2_SECONDS == 300
    assert Config.SPAM_TIMEOUT_3_SECONDS == 1800
    assert Config.DUPLICATE_MESSAGE_THRESHOLD == 4
    assert Config.MASS_MENTION_THRESHOLD == 8
