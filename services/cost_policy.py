from __future__ import annotations

import os

from config import Config


class CostPolicy:
    """Relative cost estimator for routing telemetry.

    Values are intentionally relative units, not provider price claims. They can
    be calibrated later without changing routing behavior.

    GPT-6 uses the same Luna model name for LIGHT, STANDARD and ADVANCED. Therefore
    model name alone is insufficient to select a weight; callers should provide
    route and/or reasoning_effort. Ambiguous Luna calls fall back to
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
        # One model serves all tiers; route/effort are authoritative.
        if route == "deep-reasoning":
            return cls._weight("AI_COST_WEIGHT_REASONING", 3.0)
        if route in cls.LIGHT_ROUTES:
            return cls._weight("AI_COST_WEIGHT_FAST", 0.5)
        if route in cls.STANDARD_ROUTES:
            return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)
        # Unknown routes fall back to effort; model names do not identify tiers.
        if reasoning_effort == Config.DEEP_REASONING_EFFORT:
            return cls._weight("AI_COST_WEIGHT_REASONING", 3.0)
        if reasoning_effort == Config.FAST_REASONING_EFFORT:
            return cls._weight("AI_COST_WEIGHT_FAST", 0.5)
        # A model-only call is deliberately classified as standard.
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
