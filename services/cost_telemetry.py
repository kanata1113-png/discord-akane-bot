from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
    completed: bool = True
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["created_at"] is None:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
        return {k: v for k, v in payload.items() if v is not None}


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

    def summary(self, *, since: datetime | None = None) -> dict[str, Any]:
        events = self.snapshot()
        if since is not None:
            events = [e for e in events if datetime.fromisoformat(e.created_at or datetime.now(timezone.utc).isoformat()) >= since]
        # GPT-6 light and standard tiers intentionally share Luna, so route
        # class—not model name—must distinguish their operational usage.
        light_routes = {"normal-chat"}
        standard_routes = {"reasoning", "regulation", "long-question"}
        luna_low = sum(1 for e in events if e.route in light_routes and e.model == Config.FAST_MODEL)
        luna_high = sum(1 for e in events if e.route in standard_routes and e.model == Config.CHAT_MODEL)
        sol = sum(1 for e in events if e.model == Config.REASONING_MODEL)
        total = len(events)
        input_tokens = sum(e.input_tokens for e in events)
        output_tokens = sum(e.output_tokens for e in events)
        cached_tokens = sum(e.cached_tokens for e in events)
        completed = sum(1 for e in events if e.completed)
        latencies = [e.latency_ms for e in events if e.latency_ms is not None]
        return {
            "requests": total,
            "luna": luna_low + luna_high,
            "luna_low": luna_low,
            "luna_high": luna_high,
            # Deprecated compatibility alias for pre-GPT-6 dashboards.
            "terra": luna_high,
            "sol": sol,
            "luna_rate": round((luna_low + luna_high) / total * 100, 1) if total else 0.0,
            "luna_low_rate": round(luna_low / total * 100, 1) if total else 0.0,
            "luna_high_rate": round(luna_high / total * 100, 1) if total else 0.0,
            "terra_rate": round(luna_high / total * 100, 1) if total else 0.0,
            "sol_rate": round(sol / total * 100, 1) if total else 0.0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "avg_input_tokens": round(input_tokens / total, 1) if total else 0.0,
            "avg_output_tokens": round(output_tokens / total, 1) if total else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "completion_rate": round(completed / total * 100, 1) if total else 0.0,
            "cache_rate": round(cached_tokens / input_tokens * 100, 1) if input_tokens else 0.0,
            "estimated_cost_units": round(sum(e.estimated_cost_units or 0 for e in events), 3),
        }

    def previous_month_summary(self) -> dict[str, Any]:
        now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        current_start = now_jst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_start = (current_start - timedelta(days=1)).replace(day=1)
        start_utc = previous_start.astimezone(timezone.utc)
        end_utc = current_start.astimezone(timezone.utc)
        events = [
            e for e in self.snapshot()
            if start_utc <= datetime.fromisoformat(e.created_at or datetime.now(timezone.utc).isoformat()) < end_utc
        ]
        input_tokens = sum(e.input_tokens for e in events)
        output_tokens = sum(e.output_tokens for e in events)
        return {
            "requests": len(events),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    @staticmethod
    def estimate_actual_units(model: str, input_tokens: int, output_tokens: int) -> float:
        # Relative units until provider pricing is explicitly configured.
        return round(CostPolicy.model_weight(model) * (input_tokens + output_tokens) / 1000.0, 3)


    @staticmethod
    def month_start_utc() -> datetime:
        now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        start_jst = now_jst.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_jst.astimezone(timezone.utc)
