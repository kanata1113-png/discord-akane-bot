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

    Adaptation deliberately preserves the verified Terra default baseline.
    Only clearly safe short Luna requests and unusually long standard/deep
    requests are adjusted. Expanded requests keep completion-oriented ceilings.
    """

    DEFAULTS = {
        Config.FAST_MODEL: (420, 700),
        Config.CHAT_MODEL: (840, 1200),
        Config.REASONING_MODEL: (1680, 2400),
    }
    COMPACT = {
        Config.FAST_MODEL: (280, 500),
        Config.CHAT_MODEL: (520, 800),
        Config.REASONING_MODEL: (900, 1400),
    }
    EXPANDED = {
        Config.FAST_MODEL: (700, 1000),
        Config.CHAT_MODEL: (1200, Config.REASONING_MAX_TOKENS),
        Config.REASONING_MODEL: (2200, 3000),
    }

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

        chars, tokens = table.get(model, table[Config.FAST_MODEL])
        reason = f"output_budget_{detail_level}"
        length = max(0, int(message_length or 0))

        if detail_level == "default":
            if model == Config.FAST_MODEL and length and length <= 40:
                tokens = 600
                reason += "_short"
            elif model == Config.CHAT_MODEL and length >= 500:
                tokens = 1500
                reason += "_long"
            elif model == Config.REASONING_MODEL and length >= 500:
                tokens = 2800
                reason += "_long"
        elif detail_level == "compact" and length and length <= 40:
            tokens = max(400, tokens - 100)
            reason += "_short"

        return OutputBudget(min(tokens, route_cap), chars, reason)
