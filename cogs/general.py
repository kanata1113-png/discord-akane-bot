from cogs.general_commands import GeneralCog


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))


__all__ = ["GeneralCog", "setup"]
