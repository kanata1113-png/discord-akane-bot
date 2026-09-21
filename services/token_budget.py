from __future__ import annotations

from dataclasses import dataclass

from config import Config


@dataclass(frozen=True)
class TokenBudget:
    route: str
    max_output_tokens: int
    reason: str


class TokenBudgetPolicy:
    """Conservative adaptive output budgets bounded by existing hard caps."""

    @staticmethod
    def for_request(route: str, content: str) -> TokenBudget:
        text = (content or "").strip()
        length = len(text)

        if route == "deep-reasoning":
            if length < 180:
                return TokenBudget(route, min(2400, Config.DEEP_REASONING_MAX_TOKENS), "short_deep")
            return TokenBudget(route, Config.DEEP_REASONING_MAX_TOKENS, "deep_cap")

        if route in {"reasoning", "regulation", "long-question"}:
            if length < 120:
                return TokenBudget(route, min(1600, Config.REASONING_MAX_TOKENS), "short_reasoning")
            if length < 500:
                return TokenBudget(route, min(1800, Config.REASONING_MAX_TOKENS), "medium_reasoning")
            return TokenBudget(route, Config.REASONING_MAX_TOKENS, "reasoning_cap")

        if length < 80:
            return TokenBudget(route, min(900, Config.NORMAL_CHAT_MAX_TOKENS), "short_chat")
        if length < 240:
            return TokenBudget(route, min(1200, Config.NORMAL_CHAT_MAX_TOKENS), "medium_chat")
        return TokenBudget(route, Config.NORMAL_CHAT_MAX_TOKENS, "chat_cap")
