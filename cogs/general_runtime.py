from __future__ import annotations

from cogs.community_v4 import GeneralCog as _GeneralRuntimeCog


# Stable production runtime name. Release-labelled strangler modules remain
# implementation details until the final legacy deletion pass.
GeneralCog = _GeneralRuntimeCog


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))


__all__ = ["GeneralCog", "setup"]
