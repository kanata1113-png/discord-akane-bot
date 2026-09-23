from benchmarks.quality_cost_evaluator_v01 import QualityCostCase, evaluate
from config import Config
from services.cost_policy import CostPolicy
from services.gpt6_admin_diagnostics import _tier_rows
from services.production_baseline import ADMIN_READ_ONLY_SLASH_PATHS
from services.routing_metrics import RoutingMetric, RoutingTelemetry


def test_cost_policy_distinguishes_shared_luna_tiers(monkeypatch):
    monkeypatch.setenv("AI_COST_WEIGHT_FAST", "0.5")
    monkeypatch.setenv("AI_COST_WEIGHT_CHAT", "1.0")

    assert CostPolicy.model_weight(
        Config.FAST_MODEL,
        route="normal-chat",
        reasoning_effort="low",
    ) == 0.5
    assert CostPolicy.model_weight(
        Config.CHAT_MODEL,
        route="reasoning",
        reasoning_effort="high",
    ) == 1.0
    # Ambiguous shared Luna calls must not silently under-estimate cost.
    assert CostPolicy.model_weight(Config.FAST_MODEL) == 1.0


def test_routing_telemetry_exposes_gpt6_three_tiers():
    telemetry = RoutingTelemetry()
    telemetry.emit(RoutingMetric(
        mode="production",
        source="jev",
        legacy_route="normal-chat",
        selected_route="normal-chat",
        model=Config.FAST_MODEL,
        reasoning_effort=Config.FAST_REASONING_EFFORT,
    ))
    telemetry.emit(RoutingMetric(
        mode="production",
        source="jev",
        legacy_route="reasoning",
        selected_route="reasoning",
        model=Config.CHAT_MODEL,
        reasoning_effort=Config.CHAT_REASONING_EFFORT,
    ))
    telemetry.emit(RoutingMetric(
        mode="production",
        source="jev",
        legacy_route="deep-reasoning",
        selected_route="deep-reasoning",
        model=Config.REASONING_MODEL,
        reasoning_effort=Config.DEEP_REASONING_EFFORT,
    ))

    summary = telemetry.summary()
    assert summary["by_tier"] == {
        "light": 1,
        "normal": 1,
        "advanced": 1,
        "unknown": 0,
    }
    assert summary["by_route"]["normal-chat"] == 1
    assert summary["by_route"]["reasoning"] == 1
    assert summary["by_route"]["deep-reasoning"] == 1


def test_dashboard_rows_use_tiers_not_model_names():
    rows = _tier_rows({
        "requests": 10,
        "by_tier": {"light": 5, "normal": 3, "advanced": 2},
    })
    assert rows[0][:4] == ("LIGHT", "gpt-6-luna / low", 5, 50.0)
    assert rows[1][:4] == ("NORMAL", "gpt-6-luna / high", 3, 30.0)
    assert rows[2][:4] == ("ADVANCED", "gpt-6-sol / medium", 2, 20.0)


def test_admin_diagnostic_baseline_uses_real_dashboard_name():
    assert "/admin ai_usagedashboard" in ADMIN_READ_ONLY_SLASH_PATHS
    assert "/admin ai_cost" not in ADMIN_READ_ONLY_SLASH_PATHS


def test_quality_cost_evaluator_distinguishes_luna_effort():
    result = evaluate(QualityCostCase(
        expected_model="gpt-6-luna",
        actual_model="gpt-6-luna",
        expected_reasoning_effort="high",
        actual_reasoning_effort="low",
        completed=True,
        latency_ms=100,
        cost_units=1.0,
    ))
    assert result.route_match is False


def test_admin_runtime_installs_gpt6_dashboard_callback():
    import cogs.admin as admin_entrypoint

    children = getattr(admin_entrypoint.AdminCommands, "__discord_app_commands_group_children__", ())
    dashboard = next(command for command in children if command.name == "ai_usagedashboard")
    assert dashboard.callback.__module__ == "services.gpt6_admin_diagnostics"
    assert dashboard.callback.__name__ == "_usage_dashboard"
