from __future__ import annotations

from dataclasses import dataclass, replace

from config import Config
from services.orchestration_context import OrchestrationContext
from services.routing_policy import RouteSelection


@dataclass(frozen=True)
class FollowupDowngradeDecision:
    applied: bool
    reason: str


class FollowupDowngradePolicy:
    LIGHT_MARKERS = (
        "要点", "一言", "例を1つ", "例を一つ", "短く", "簡潔", "つまり", "結論だけ", "簡単に",
    )

    @classmethod
    def apply(cls, selection: RouteSelection, context: OrchestrationContext) -> tuple[RouteSelection, FollowupDowngradeDecision]:
        if not context.external.followup_like:
            return selection, FollowupDowngradeDecision(False, "not_followup")
        if context.regulation_mode or context.requested_format == "detailed":
            return selection, FollowupDowngradeDecision(False, "protected_context")
        text = context.content
        if len(text) > 60 or not any(marker in text for marker in cls.LIGHT_MARKERS):
            return selection, FollowupDowngradeDecision(False, "not_lightweight")
        if selection.model == Config.REASONING_MODEL:
            return replace(
                selection,
                model=Config.CHAT_MODEL,
                reasoning_effort=Config.CHAT_REASONING_EFFORT,
                route="reasoning",
                max_output_tokens=min(selection.max_output_tokens, Config.REASONING_MAX_TOKENS),
                fallback_reason="light_followup_downgrade",
            ), FollowupDowngradeDecision(True, "sol_to_luna_high")
        if selection.route in {"reasoning", "long-question"}:
            return replace(
                selection,
                model=Config.FAST_MODEL,
                reasoning_effort=Config.FAST_REASONING_EFFORT,
                route="normal-chat",
                max_output_tokens=min(selection.max_output_tokens, Config.NORMAL_CHAT_MAX_TOKENS),
                fallback_reason="light_followup_downgrade",
            ), FollowupDowngradeDecision(True, "luna_high_to_luna_low")
        return selection, FollowupDowngradeDecision(False, "already_lowest")
