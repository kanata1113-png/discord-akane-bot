from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass(frozen=True)
class OutputBudget:
    max_output_tokens: int
    target_characters: int
    reason: str


class OutputBudgetPolicy:
    """Cost-conscious soft character targets backed by conservative token caps.

    GPT-6 uses Luna for both light and standard work, differentiated by reasoning
    effort. Budget lookup therefore must not use model name alone: light and
    standard Luna keep distinct output envelopes. Sol remains the deep tier.
    """

    DEFAULTS = {
        "light": (420, 700),
        "standard": (840, 1200),
        "deep": (1680, 2400),
    }
    COMPACT = {
        "light": (280, 500),
        "standard": (520, 800),
        "deep": (900, 1400),
    }
    EXPANDED = {
        "light": (700, 1000),
        "standard": (1200, Config.REASONING_MAX_TOKENS),
        "deep": (2200, 3000),
    }

    @staticmethod
    def _tier_key(model: str, route_cap: int) -> str:
        if model == Config.REASONING_MODEL:
            return "deep"
        # FAST_MODEL and CHAT_MODEL intentionally share gpt-6-luna. Their
        # configured route caps remain distinct and preserve the light/standard
        # output budgets without coupling behavior to a model-name difference.
        if route_cap > Config.NORMAL_CHAT_MAX_TOKENS:
            return "standard"
        return "light"

    @classmethod
    def for_request(
        cls,
        model: str,
        detail_level: str,
        route_cap: int,
        *,
        message_length: int | None = None,
    ) -> OutputBudget:
        table = cls.DEFAULTS
        if detail_level == "compact":
            table = cls.COMPACT
        elif detail_level == "expanded":
            table = cls.EXPANDED

        tier = cls._tier_key(model, route_cap)
        chars, tokens = table[tier]
        reason = f"output_budget_{detail_level}"
        length = max(0, int(message_length or 0))

        if detail_level == "default":
            if tier == "light" and length and length <= 40:
                tokens = 600
                reason += "_short"
            elif tier == "standard" and length >= 500:
                tokens = 1500
                reason += "_long"
            elif tier == "deep" and length >= 500:
                tokens = 2800
                reason += "_long"
        elif detail_level == "compact" and length and length <= 40:
            tokens = max(400, tokens - 100)
            reason += "_short"

        return OutputBudget(min(tokens, route_cap), chars, reason)
