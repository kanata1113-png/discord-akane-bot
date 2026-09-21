from __future__ import annotations

import os
from dataclasses import dataclass

from config import Config
from services.orchestration_context import OrchestrationContext
from services.token_budget import TokenBudgetPolicy


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BudgetDecision:
    route: str
    max_output_tokens: int
    hard_cap: int
    reason: str
    controller_enabled: bool


class BudgetController:
    """Context-aware output budget controller bounded by existing hard caps.

    The v2 controller uses its own feature gate so it can be developed and
    evaluated without changing the existing v1 adaptive-budget behavior.
    """

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = (
            _env_flag("AI_BUDGET_CONTROLLER_V2", False)
            if enabled is None
            else bool(enabled)
        )

    @staticmethod
    def hard_cap(route: str) -> int:
        if route == "deep-reasoning":
            return Config.DEEP_REASONING_MAX_TOKENS
        if route in {"reasoning", "regulation", "long-question"}:
            return Config.REASONING_MAX_TOKENS
        return Config.NORMAL_CHAT_MAX_TOKENS

    def decide(self, route: str, context: OrchestrationContext) -> BudgetDecision:
        cap = self.hard_cap(route)
        if not self.enabled:
            return BudgetDecision(route, cap, cap, "controller_disabled", False)

        base = TokenBudgetPolicy.for_request(route, context.content)
        tokens = min(base.max_output_tokens, cap)
        reason = base.reason

        if context.requested_format == "detailed":
            tokens = cap
            reason = "requested_detail_cap"
        elif context.requested_format == "short":
            tokens = min(tokens, 900 if route == "normal-chat" else 1400)
            reason = "requested_short"
        elif context.current_intent in {"translation-like", "definition-like"}:
            tokens = min(tokens, 1200)
            reason = f"intent_{context.current_intent}"

        return BudgetDecision(route, tokens, cap, reason, True)
