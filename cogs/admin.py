import cogs.admin_commands as _admin_commands
from cogs.admin_runtime import AdminCommands
from services.gpt6_admin_diagnostics import install_gpt6_admin_diagnostics


# Preserve the Phase 6 public-class identity contract while the stable runtime
# owns migrated moderation behavior.
install_gpt6_admin_diagnostics(AdminCommands)
_admin_commands.AdminCommands = AdminCommands


async def setup(bot):
    bot.tree.add_command(AdminCommands(bot))


__all__ = ["AdminCommands", "setup"]
