from __future__ import annotations

import os

from config import Config


class CostPolicy:
    """Relative cost estimator for routing telemetry.

    Values are intentionally relative units, not provider price claims. They can
    be calibrated later without changing routing behavior.

    GPT-6 uses the same Luna model name for both LIGHT and NORMAL. Therefore
    model name alone is insufficient to select a weight; callers should provide
    route and/or reasoning_effort. Ambiguous Luna calls fail conservatively to
    the standard/chat weight instead of silently underestimating usage.
    """

    LIGHT_ROUTES = frozenset({"normal-chat"})
    STANDARD_ROUTES = frozenset({"reasoning", "regulation", "long-question"})

    @staticmethod
    def _weight(name: str, default: float) -> float:
        try:
            value = float(os.getenv(name, str(default)))
        except ValueError:
            return default
        return value if value > 0 else default

    @classmethod
    def model_weight(
        cls,
        model: str,
        *,
        route: str | None = None,
        reasoning_effort: str | None = None,
    ) -> float:
        if model == Config.REASONING_MODEL:
            return cls._weight("AI_COST_WEIGHT_REASONING", 3.0)

        if model == Config.FAST_MODEL == Config.CHAT_MODEL:
            if reasoning_effort == Config.FAST_REASONING_EFFORT or route in cls.LIGHT_ROUTES:
                return cls._weight("AI_COST_WEIGHT_FAST", 0.5)
            if reasoning_effort == Config.CHAT_REASONING_EFFORT or route in cls.STANDARD_ROUTES:
                return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)
            return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)

        if model == Config.FAST_MODEL:
            return cls._weight("AI_COST_WEIGHT_FAST", 0.5)
        if model == Config.CHAT_MODEL:
            return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)
        return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)

    @classmethod
    def estimate_units(
        cls,
        model: str,
        max_output_tokens: int,
        *,
        route: str | None = None,
        reasoning_effort: str | None = None,
    ) -> float:
        return round(
            cls.model_weight(
                model,
                route=route,
                reasoning_effort=reasoning_effort,
            )
            * max_output_tokens
            / 1000.0,
            3,
        )
