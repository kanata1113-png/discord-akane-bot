from dataclasses import replace

from config import Config
from services.followup_downgrade import FollowupDowngradePolicy
from services.orchestration_context import OrchestrationContextBuilder
from services.output_budget import OutputBudgetPolicy
from services.routing_policy import RoutingPolicy


def test_gpt6_router_contract():
    assert Config.FAST_MODEL == "gpt-6-luna"
    assert Config.FAST_REASONING_EFFORT == "low"
    assert Config.CHAT_MODEL == "gpt-6-luna"
    assert Config.CHAT_REASONING_EFFORT == "high"
    assert Config.REASONING_MODEL == "gpt-6-sol"
    assert Config.REASONING_EFFORT == "medium"
    assert Config.DEEP_REASONING_EFFORT == "medium"


def test_gpt6_route_assignments_keep_three_effort_tiers():
    light = RoutingPolicy.tier_for_route("normal-chat")
    standard = RoutingPolicy.tier_for_route("reasoning")
    deep = RoutingPolicy.tier_for_route("deep-reasoning")

    assert (light.model, light.reasoning_effort) == ("gpt-6-luna", "low")
    assert (standard.model, standard.reasoning_effort) == ("gpt-6-luna", "high")
    assert (deep.model, deep.reasoning_effort) == ("gpt-6-sol", "medium")


def test_shared_luna_model_keeps_distinct_output_budgets():
    light = OutputBudgetPolicy.for_request(
        Config.FAST_MODEL, "default", Config.NORMAL_CHAT_MAX_TOKENS
    )
    standard = OutputBudgetPolicy.for_request(
        Config.CHAT_MODEL, "default", Config.REASONING_MAX_TOKENS
    )

    assert light.target_characters == 420
    assert light.max_output_tokens == 700
    assert standard.target_characters == 840
    assert standard.max_output_tokens == 1200


def test_normal_chat_followup_is_not_falsely_downgraded_by_shared_model_name():
    history = [{"role": "user", "content": "こんにちは"}, {"role": "assistant", "content": "やあ"}]
    context = OrchestrationContextBuilder.build("それを短く", history)
    selection = RoutingPolicy.legacy_selection("こんにちは")
    result, decision = FollowupDowngradePolicy.apply(selection, context)

    assert not decision.applied
    assert result.route == "normal-chat"
    assert result.reasoning_effort == "low"


def test_standard_followup_downgrades_effort_even_when_model_name_is_same():
    history = [{"role": "user", "content": "比較して"}, {"role": "assistant", "content": "回答"}]
    context = OrchestrationContextBuilder.build("それを短く、要点だけ", history)
    selection = RoutingPolicy.legacy_selection("メリットとデメリットを比較して")

    assert selection.model == Config.CHAT_MODEL
    assert selection.reasoning_effort == "high"

    result, decision = FollowupDowngradePolicy.apply(selection, context)

    assert decision.applied
    assert result.model == Config.FAST_MODEL
    assert result.reasoning_effort == "low"
    assert result.route == "normal-chat"


def test_weak_deep_route_demotes_to_luna_high():
    from services.sol_promotion import SolPromotionGate

    selection = RoutingPolicy.legacy_selection("徹底的に")
    selection = replace(selection, model=Config.REASONING_MODEL, route="deep-reasoning")
    result, decision = SolPromotionGate.apply(selection, "徹底的に説明して")

    assert not decision.promoted
    assert result.model == "gpt-6-luna"
    assert result.reasoning_effort == "high"
    assert result.route == "reasoning"
