import cogs.general_commands as _general_commands
from cogs.general_runtime import GeneralCog


# Preserve the Phase 6 public-class identity contract while the stable v4
# runtime owns production behavior. Historical release-labelled modules remain
# implementation details and are no longer part of the public extension path.
_general_commands.GeneralCog = GeneralCog


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))


__all__ = ["GeneralCog", "setup"]
