import cogs.admin_commands as _admin_commands
from cogs.admin_runtime import AdminCommands


# Preserve the Phase 6 public-class identity contract while the stable runtime
# owns migrated moderation behavior.
_admin_commands.AdminCommands = AdminCommands


async def setup(bot):
    bot.tree.add_command(AdminCommands(bot))


__all__ = ["AdminCommands", "setup"]
