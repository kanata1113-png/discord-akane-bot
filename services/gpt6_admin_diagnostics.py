from __future__ import annotations

from collections.abc import Callable

import discord

from config import Config


TIER_TARGETS = (
    ("LIGHT", "light", Config.FAST_MODEL, Config.FAST_REASONING_EFFORT, 45, 60),
    ("NORMAL", "normal", Config.CHAT_MODEL, Config.CHAT_REASONING_EFFORT, 25, 35),
    ("ADVANCED", "advanced", Config.REASONING_MODEL, Config.DEEP_REASONING_EFFORT, 10, 20),
)


def _command(group_cls, name: str):
    for command in getattr(group_cls, "__discord_app_commands_group_children__", ()):  # discord.py group registry
        if getattr(command, "name", None) == name:
            return command
    raise RuntimeError(f"admin command not found: {name}")


def _tier_rows(routes: dict) -> list[tuple[str, str, int, float, int, int, str]]:
    total = int(routes.get("requests", 0) or 0)
    by_tier = routes.get("by_tier") or {}
    rows = []
    for label, tier, model, effort, low, high in TIER_TARGETS:
        count = int(by_tier.get(tier, 0) or 0)
        rate = round(count / total * 100, 1) if total else 0.0
        status = "✅" if total and low <= rate <= high else ("⏳" if not total else "⚠️")
        rows.append((label, f"{model} / {effort}", count, rate, low, high, status))
    return rows


async def _usage_dashboard(self, interaction: discord.Interaction) -> None:
    executor = getattr(self.bot.ai, "executor", None)
    telemetry = getattr(executor, "cost_telemetry", None)
    routing = getattr(self.bot.ai, "routing_telemetry", None)
    since = telemetry.month_start_utc() if telemetry else None
    usage = telemetry.summary(since=since) if telemetry else {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    previous_usage = telemetry.previous_month_summary() if telemetry else {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    routes = routing.summary(since=since) if routing else {
        "requests": 0,
        "by_tier": {},
        "jev_decisions": 0,
        "fallbacks": 0,
        "low_confidence": 0,
        "jev_errors": 0,
        "avg_jev_latency_ms": 0.0,
    }

    total = int(routes.get("requests", 0) or 0)
    rows = _tier_rows(routes)
    statuses = [row[-1] for row in rows]
    balance = (
        "⏳ COLLECTING DATA"
        if not total
        else ("✅ HEALTHY" if all(status == "✅" for status in statuses) else "⚠️ WATCH")
    )
    advanced_state = (
        "⏳ COLLECTING DATA"
        if not total
        else ("✅ IN RANGE" if rows[2][-1] == "✅" else "⚠️ OUT OF RANGE")
    )
    router_health = "✅ HEALTHY" if routes.get("jev_errors", 0) == 0 else "⚠️ CHECK"

    embed = discord.Embed(
        title="🌸 Akane AI Usage Dashboard",
        description="当月のAI利用量とGPT-6 Production Routerの稼働状況",
        color=discord.Color.red(),
    )
    embed.add_field(
        name="📊 AI USAGE",
        value=(
            f"Requests **{usage['requests']:,}**\n"
            f"Input **{usage['input_tokens']:,}** / Output **{usage['output_tokens']:,}** tokens\n"
            f"Total **{usage['input_tokens'] + usage['output_tokens']:,}** tokens"
        ),
        inline=False,
    )

    current_ratio = usage["input_tokens"] / usage["output_tokens"] if usage["output_tokens"] else 0.0
    previous_ratio = (
        previous_usage["input_tokens"] / previous_usage["output_tokens"]
        if previous_usage["output_tokens"]
        else 0.0
    )
    avg_input = usage["input_tokens"] / usage["requests"] if usage["requests"] else 0.0
    avg_output = usage["output_tokens"] / usage["requests"] if usage["requests"] else 0.0
    if previous_ratio > 0:
        ratio_change = (current_ratio / previous_ratio - 1) * 100
        efficiency_status = "⚠️ WATCH" if ratio_change >= 50 else "✅ STABLE"
        baseline_line = f"Previous month **{previous_ratio:.1f}×** · Change **{ratio_change:+.1f}%**"
    else:
        efficiency_status = "⏳ COLLECTING BASELINE"
        baseline_line = "Previous month **no baseline yet**"

    embed.add_field(
        name="⚡ TOKEN EFFICIENCY",
        value=(
            f"Input / Output **{current_ratio:.1f}×**\n"
            f"Avg Input/request **{avg_input:,.0f}** · Output **{avg_output:,.0f}**\n"
            f"{baseline_line}\n"
            f"Efficiency **{efficiency_status}**"
        ),
        inline=False,
    )
    embed.add_field(
        name="🧠 GPT-6 ROUTING",
        value="\n".join(
            f"{label} `{model_effort}` · **{count:,}** · **{rate}%**"
            for label, model_effort, count, rate, _, _, _ in rows
        ),
        inline=False,
    )
    embed.add_field(
        name="🎯 TARGET RANGE",
        value="\n".join(
            f"{status} {label} **{rate}%** · target {low}–{high}%"
            for label, _, _, rate, low, high, status in rows
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ ROUTER HEALTH",
        value=(
            f"Jev decisions **{routes.get('jev_decisions', 0):,}**\n"
            f"Fallbacks **{routes.get('fallbacks', 0):,}** · Low confidence **{routes.get('low_confidence', 0):,}**\n"
            f"Jev errors **{routes.get('jev_errors', 0):,}** · Avg latency **{routes.get('avg_jev_latency_ms', 0.0):,.1f} ms**"
        ),
        inline=False,
    )
    embed.add_field(
        name="📌 STATUS",
        value=(
            f"Routing balance **{balance}**\n"
            f"ADVANCED usage **{advanced_state}**\n"
            f"Jev Router **{router_health}**"
        ),
        inline=False,
    )
    embed.set_footer(text="集計期間: 毎月1日 00:00 JST〜現在 / runtime履歴 最大1000件")
    await interaction.response.send_message(embed=embed, ephemeral=True)


def _status_wrapper(original: Callable):
    async def wrapped(self, interaction: discord.Interaction) -> None:
        await original(self, interaction)
        if not interaction.response.is_done():
            return
        try:
            message = await interaction.original_response()
            if not message.embeds:
                return
            embed = message.embeds[0].copy()
            for index, field in enumerate(embed.fields):
                if field.name == "🧠 AI":
                    embed.set_field_at(
                        index,
                        name="🧠 AI",
                        value=(
                            f"LIGHT: `{Config.FAST_MODEL}` / `{Config.FAST_REASONING_EFFORT}`\n"
                            f"NORMAL: `{Config.CHAT_MODEL}` / `{Config.CHAT_REASONING_EFFORT}`\n"
                            f"ADVANCED: `{Config.REASONING_MODEL}` / `{Config.DEEP_REASONING_EFFORT}`"
                        ),
                        inline=False,
                    )
                    await interaction.edit_original_response(embed=embed)
                    return
        except Exception:
            # Diagnostics must never break an otherwise successful admin status response.
            return

    return wrapped


def install_gpt6_admin_diagnostics(group_cls) -> None:
    """Patch two legacy read-only admin diagnostics without touching mutations.

    AdminCommands is still a strangler-compatible legacy Group. Until that file
    is retired, this narrow compatibility seam updates only read-only callbacks
    whose old implementation assumed three distinct model names.
    """
    if getattr(group_cls, "_gpt6_diagnostics_installed", False):
        return

    status_command = _command(group_cls, "status")
    dashboard_command = _command(group_cls, "ai_usagedashboard")
    status_command._callback = _status_wrapper(status_command.callback)
    dashboard_command._callback = _usage_dashboard
    group_cls._gpt6_diagnostics_installed = True
