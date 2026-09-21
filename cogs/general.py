import cogs.general_commands as _general_commands
from cogs.general_v4 import GeneralCog


# Preserve the Phase 6 public-class identity contract while the Release C
# strangler subclass owns migrated behavior. Consumers importing either
# entrypoint observe the same class object.
_general_commands.GeneralCog = GeneralCog


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))


__all__ = ["GeneralCog", "setup"]
