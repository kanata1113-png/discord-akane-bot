from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any

from config import Config
from services.cost_policy import CostPolicy


logger = logging.getLogger("AkaneBot")


@dataclass(frozen=True)
class UsageEvent:
    model: str
    route: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: int | None = None
    estimated_cost_units: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class CostTelemetry:
    """Metadata-only bounded runtime usage telemetry. No prompt/user text is stored."""

    def __init__(self, max_events: int = 1000) -> None:
        self._events: deque[UsageEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: UsageEvent) -> None:
        with self._lock:
            self._events.append(event)
        logger.info("AI_USAGE_METRIC %s", json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")))

    def snapshot(self) -> list[UsageEvent]:
        with self._lock:
            return list(self._events)

    def summary(self) -> dict[str, Any]:
        events = self.snapshot()
        by_model = {Config.FAST_MODEL: 0, Config.CHAT_MODEL: 0, Config.REASONING_MODEL: 0}
        for event in events:
            by_model[event.model] = by_model.get(event.model, 0) + 1
        total = len(events)
        return {
            "requests": total,
            "luna": by_model.get(Config.FAST_MODEL, 0),
            "terra": by_model.get(Config.CHAT_MODEL, 0),
            "sol": by_model.get(Config.REASONING_MODEL, 0),
            "sol_rate": round(by_model.get(Config.REASONING_MODEL, 0) / total * 100, 1) if total else 0.0,
            "input_tokens": sum(e.input_tokens for e in events),
            "output_tokens": sum(e.output_tokens for e in events),
            "estimated_cost_units": round(sum(e.estimated_cost_units or 0 for e in events), 3),
        }

    @staticmethod
    def estimate_actual_units(model: str, input_tokens: int, output_tokens: int) -> float:
        # Relative units until provider pricing is explicitly configured.
        return round(CostPolicy.model_weight(model) * (input_tokens + output_tokens) / 1000.0, 3)
