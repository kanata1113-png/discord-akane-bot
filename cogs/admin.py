from cogs.admin_commands import AdminCommands


async def setup(bot):
    bot.tree.add_command(AdminCommands(bot))


__all__ = ["AdminCommands", "setup"]
