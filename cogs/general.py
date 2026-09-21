import cogs.general_commands as _general_commands
from cogs.community_v4 import GeneralCog


# Preserve the Phase 6 public-class identity contract while layered v4
# stranglers own migrated behavior. Consumers importing either entrypoint
# observe the same class object.
_general_commands.GeneralCog = GeneralCog


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))


__all__ = ["GeneralCog", "setup"]
