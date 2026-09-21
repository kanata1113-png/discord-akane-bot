from dataclasses import replace

from config import Config
from services.cost_telemetry import CostTelemetry, UsageEvent
from services.followup_downgrade import FollowupDowngradePolicy
from services.history_optimizer import HistoryOptimizer
from services.orchestration_context import OrchestrationContextBuilder
from services.output_budget import OutputBudgetPolicy
from services.routing_policy import RoutingPolicy
from services.sol_promotion import SolPromotionGate


def test_history_optimizer_passthrough_for_small_context():
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    result = HistoryOptimizer.optimize(history)
    assert result.mode == "passthrough"
    assert result.messages == history


def test_history_optimizer_compresses_large_old_context_and_keeps_recent_verbatim():
    history = []
    for index in range(12):
        history.append({"role": "user" if index % 2 == 0 else "assistant", "content": f"m{index}:" + ("x" * 900)})
    result = HistoryOptimizer.optimize(history)
    assert result.mode == "compressed"
    assert result.optimized_characters < result.original_characters
    assert result.messages[-6:] == history[-6:]
    assert "過去会話の圧縮メモ" in result.messages[0]["content"]


def test_light_followup_can_downgrade_terra_to_luna():
    history = [{"role": "user", "content": "比較して"}, {"role": "assistant", "content": "回答"}]
    context = OrchestrationContextBuilder.build("それを短く、要点だけ", history)
    selection = RoutingPolicy.legacy_selection("メリットとデメリットを比較して")
    assert selection.model == Config.CHAT_MODEL
    downgraded, decision = FollowupDowngradePolicy.apply(selection, context)
    assert decision.applied
    assert downgraded.model == Config.FAST_MODEL
    assert downgraded.route == "normal-chat"


def test_detailed_followup_is_not_downgraded():
    history = [{"role": "user", "content": "比較して"}, {"role": "assistant", "content": "回答"}]
    context = OrchestrationContextBuilder.build("それを詳しく", history)
    selection = RoutingPolicy.legacy_selection("メリットとデメリットを比較して")
    downgraded, decision = FollowupDowngradePolicy.apply(selection, context)
    assert not decision.applied
    assert downgraded.model == selection.model


def test_adaptive_default_output_budget_uses_request_length():
    short = OutputBudgetPolicy.for_request(Config.FAST_MODEL, "default", 1500, message_length=20)
    standard = OutputBudgetPolicy.for_request(Config.FAST_MODEL, "default", 1500, message_length=100)
    assert short.max_output_tokens == 600
    assert standard.max_output_tokens == 700


def test_expanded_terra_keeps_completion_cap():
    expanded = OutputBudgetPolicy.for_request(Config.CHAT_MODEL, "expanded", 2000, message_length=20)
    assert expanded.max_output_tokens == 2000


def test_sol_score_requires_more_than_one_generic_depth_signal():
    weak = RoutingPolicy.legacy_selection("徹底的に")
    weak = replace(weak, model=Config.REASONING_MODEL, route="deep-reasoning")
    gated, decision = SolPromotionGate.apply(weak, "徹底的に説明して")
    assert not decision.promoted
    assert decision.score < 3
    assert gated.model == Config.CHAT_MODEL


def test_sol_score_keeps_structurally_complex_request():
    selection = RoutingPolicy.legacy_selection("複数の観点から厳密に比較し、根拠も示して")
    selection = replace(selection, model=Config.REASONING_MODEL, route="deep-reasoning")
    gated, decision = SolPromotionGate.apply(selection, "複数の観点から厳密に比較し、根拠も示して")
    assert decision.promoted
    assert decision.score >= 3
    assert gated.model == Config.REASONING_MODEL


def test_cost_telemetry_exposes_operational_health_metrics():
    telemetry = CostTelemetry()
    telemetry.record(UsageEvent(Config.FAST_MODEL, "normal-chat", 100, 50, 150, cached_tokens=20, latency_ms=1000, completed=True))
    telemetry.record(UsageEvent(Config.CHAT_MODEL, "reasoning", 300, 100, 400, cached_tokens=0, latency_ms=3000, completed=False))
    summary = telemetry.summary()
    assert summary["requests"] == 2
    assert summary["avg_input_tokens"] == 200.0
    assert summary["avg_output_tokens"] == 75.0
    assert summary["avg_latency_ms"] == 2000.0
    assert summary["completion_rate"] == 50.0
    assert summary["cache_rate"] == 5.0
