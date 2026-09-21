from __future__ import annotations

import os

from config import Config


class CostPolicy:
    """Relative cost estimator for routing telemetry.

    Values are intentionally relative units, not provider price claims. They can
    be calibrated later without changing routing behavior.
    """

    @staticmethod
    def _weight(name: str, default: float) -> float:
        try:
            value = float(os.getenv(name, str(default)))
        except ValueError:
            return default
        return value if value > 0 else default

    @classmethod
    def model_weight(cls, model: str) -> float:
        if model == Config.REASONING_MODEL:
            return cls._weight("AI_COST_WEIGHT_REASONING", 3.0)
        if model == Config.FAST_MODEL:
            return cls._weight("AI_COST_WEIGHT_FAST", 0.5)
        return cls._weight("AI_COST_WEIGHT_CHAT", 1.0)

    @classmethod
    def estimate_units(cls, model: str, max_output_tokens: int) -> float:
        return round(cls.model_weight(model) * max_output_tokens / 1000.0, 3)
