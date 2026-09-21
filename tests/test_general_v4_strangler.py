from cogs.general import GeneralCog
from cogs.general_v4 import LegacyGeneralCog


def test_strangler_cog_preserves_inherited_app_command_surface():
    legacy = {command.name for command in LegacyGeneralCog.__cog_app_commands__}
    migrated = {command.name for command in GeneralCog.__cog_app_commands__}

    assert migrated == legacy


def test_strangler_cog_overrides_only_migrated_command_callbacks():
    migrated_names = {
        "translate",
        "define",
        "summary",
        "remind",
        "memory",
        "forget",
        "titles",
        "title_set",
    }

    for name in migrated_names:
        migrated = getattr(GeneralCog, name)
        legacy = getattr(LegacyGeneralCog, name)
        assert migrated is not legacy

    for name in {"level", "leaderboard", "profile", "weekly", "rankings"}:
        assert getattr(GeneralCog, name) is getattr(LegacyGeneralCog, name)
