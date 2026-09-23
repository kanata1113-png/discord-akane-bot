from __future__ import annotations

import json
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from dataclasses import asdict, dataclass
from typing import Any

from config import Config


logger = logging.getLogger("AkaneBot")


@dataclass(frozen=True)
class RoutingMetric:
    mode: str
    source: str
    legacy_route: str
    selected_route: str
    jev_route: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    fallback_reason: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    max_output_tokens: int | None = None
    budget_reason: str | None = None
    history_messages: int | None = None
    followup_like: bool | None = None
    previous_route: str | None = None
    previous_intent: str | None = None
    intent_hint: str | None = None
    estimated_cost_units: float | None = None
    event_id: str | None = None
    event: str = "routing_decision"

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


class RoutingTelemetry:
    """Privacy-minimal structured telemetry for routing behavior."""

    LIGHT_ROUTES = frozenset({"normal-chat"})
    STANDARD_ROUTES = frozenset({"reasoning", "regulation", "long-question"})

    def __init__(self, max_events: int = 1000) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._lock = Lock()

    def snapshot(self, *, since: datetime | None = None) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)
        if since is None:
            return events
        return [e for e in events if datetime.fromisoformat(e['created_at']) >= since]

    @classmethod
    def tier_for_event(cls, event: dict[str, Any]) -> str:
        route = str(event.get("selected_route") or "")
        model = event.get("model")
        effort = event.get("reasoning_effort")
        if model == Config.REASONING_MODEL or route == "deep-reasoning":
            return "advanced"
        if route in cls.STANDARD_ROUTES or effort == Config.CHAT_REASONING_EFFORT:
            return "normal"
        if route in cls.LIGHT_ROUTES or effort == Config.FAST_REASONING_EFFORT:
            return "light"
        return "unknown"

    def summary(self, *, since: datetime | None = None) -> dict[str, Any]:
        events = [e for e in self.snapshot(since=since) if e.get('event') == 'routing_decision']
        total = len(events)
        by_model: dict[str, int] = {}
        by_route: dict[str, int] = {}
        by_tier = {"light": 0, "normal": 0, "advanced": 0, "unknown": 0}
        for event in events:
            model = event.get('model')
            if model:
                by_model[model] = by_model.get(model, 0) + 1
            route = str(event.get("selected_route") or "unknown")
            by_route[route] = by_route.get(route, 0) + 1
            tier = self.tier_for_event(event)
            by_tier[tier] = by_tier.get(tier, 0) + 1
        jev = sum(1 for e in events if e.get('source') == 'jev')
        fallback = sum(1 for e in events if e.get('fallback_reason'))
        low_conf = sum(1 for e in events if str(e.get('fallback_reason', '')).startswith('low_confidence'))
        errors = sum(1 for e in events if e.get('fallback_reason') and not str(e.get('fallback_reason')).startswith('low_confidence'))
        latencies = [int(e['latency_ms']) for e in events if e.get('latency_ms') is not None]
        return {
            'requests': total,
            'by_model': by_model,
            'by_route': by_route,
            'by_tier': by_tier,
            'jev_decisions': jev,
            'fallbacks': fallback,
            'low_confidence': low_conf,
            'jev_errors': errors,
            'avg_jev_latency_ms': round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        }

    @staticmethod
    def new_event_id() -> str:
        return uuid.uuid4().hex[:12]

    def emit(self, metric: RoutingMetric) -> None:
        payload = metric.to_dict()
        payload['created_at'] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._events.append(payload)
        logger.info(
            "ROUTING_METRIC %s",
            json.dumps(
                metric.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
