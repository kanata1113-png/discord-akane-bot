from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass(frozen=True)
class OutputBudget:
    max_output_tokens: int
    target_characters: int
    reason: str


class OutputBudgetPolicy:
    """Cost-conscious soft character targets backed by conservative token caps."""

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
    def for_request(cls, model: str, detail_level: str, route_cap: int) -> OutputBudget:
        table = cls.DEFAULTS
        if detail_level == "compact":
            table = cls.COMPACT
        elif detail_level == "expanded":
            table = cls.EXPANDED
        chars, tokens = table.get(model, table[Config.FAST_MODEL])
        return OutputBudget(min(tokens, route_cap), chars, f"output_budget_{detail_level}")
