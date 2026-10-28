from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

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
    reasoning_effort: str | None = None
    latency_ms: int | None = None
    estimated_cost_units: float | None = None
    completed: bool = True
    created_at: str | None = None

    # Token Efficiency Rationalization v0.1 metadata. No prompt/user text is stored.
    logical_request_id: str | None = None
    feature: str = "unknown"
    call_kind: str = "primary"
    attempt: int = 1
    system_prompt_chars: int = 0
    history_chars: int = 0
    user_chars: int = 0
    estimated_input_tokens: int = 0
    incomplete_reason: str | None = None
    error_type: str | None = None
    status_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["created_at"] is None:
            payload["created_at"] = datetime.now(timezone.utc).isoformat()
        return {k: v for k, v in payload.items() if v is not None}


class CostTelemetry:
    """Metadata-only bounded runtime usage telemetry.

    The telemetry intentionally stores only counters/lengths/route metadata.
    Prompt text, user text, and conversation content are never persisted here.
    """

    def __init__(self, max_events: int = 1000) -> None:
        self._events: deque[UsageEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: UsageEvent) -> None:
        stored = event
        if stored.created_at is None:
            stored = replace(stored, created_at=datetime.now(timezone.utc).isoformat())
        with self._lock:
            self._events.append(stored)
        logger.info(
            "AI_USAGE_METRIC %s",
            json.dumps(stored.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    def snapshot(self) -> list[UsageEvent]:
        with self._lock:
            return list(self._events)

    @staticmethod
    def _logical_key(event: UsageEvent, index: int) -> str:
        return event.logical_request_id or f"legacy-event-{index}"

    def summary(self, *, since: datetime | None = None) -> dict[str, Any]:
        events = self.snapshot()
        if since is not None:
            events = [
                e
                for e in events
                if datetime.fromisoformat(
                    e.created_at or datetime.now(timezone.utc).isoformat()
                )
                >= since
            ]

        light_routes = {"normal-chat"}
        standard_routes = {"reasoning", "regulation", "long-question"}
        luna_low = sum(
            1
            for e in events
            if e.model == Config.FAST_MODEL
            and (
                e.route in light_routes
                or e.reasoning_effort == Config.FAST_REASONING_EFFORT
            )
        )
        luna_high = sum(
            1
            for e in events
            if e.model == Config.CHAT_MODEL
            and (
                e.route in standard_routes
                or e.reasoning_effort == Config.CHAT_REASONING_EFFORT
            )
        )
        advanced = sum(1 for e in events if e.model == Config.REASONING_MODEL)

        model_calls = len(events)
        logical_keys = {
            self._logical_key(event, index)
            for index, event in enumerate(events)
        }
        logical_requests = len(logical_keys)
        retry_failover_calls = sum(
            1 for e in events if e.call_kind in {"retry", "failover"}
        )
        retry_failover_input_tokens = sum(
            e.input_tokens for e in events if e.call_kind in {"retry", "failover"}
        )

        input_tokens = sum(e.input_tokens for e in events)
        output_tokens = sum(e.output_tokens for e in events)
        cached_tokens = sum(e.cached_tokens for e in events)
        completed = sum(1 for e in events if e.completed)
        latencies = [e.latency_ms for e in events if e.latency_ms is not None]
        system_prompt_chars = sum(e.system_prompt_chars for e in events)
        history_chars = sum(e.history_chars for e in events)
        user_chars = sum(e.user_chars for e in events)
        estimated_input_tokens = sum(e.estimated_input_tokens for e in events)
        max_tokens_incomplete = sum(
            1 for e in events if e.incomplete_reason == "max_output_tokens"
        )
        same_model_max_tokens_retry = sum(
            1
            for e in events
            if e.call_kind == "retry"
            and e.incomplete_reason == "max_output_tokens"
        )

        by_feature_raw: dict[str, list[tuple[int, UsageEvent]]] = defaultdict(list)
        for index, event in enumerate(events):
            by_feature_raw[event.feature or "unknown"].append((index, event))

        by_feature: dict[str, dict[str, Any]] = {}
        for feature, rows in sorted(by_feature_raw.items()):
            feature_events = [event for _, event in rows]
            feature_logical = {
                self._logical_key(event, index)
                for index, event in rows
            }
            feature_input = sum(e.input_tokens for e in feature_events)
            feature_output = sum(e.output_tokens for e in feature_events)
            feature_history = sum(e.history_chars for e in feature_events)
            by_feature[feature] = {
                "logical_requests": len(feature_logical),
                "model_calls": len(feature_events),
                "retry_failover_calls": sum(
                    1
                    for e in feature_events
                    if e.call_kind in {"retry", "failover"}
                ),
                "input_tokens": feature_input,
                "output_tokens": feature_output,
                "avg_input_tokens": round(
                    feature_input / len(feature_events), 1
                )
                if feature_events
                else 0.0,
                "avg_history_chars": round(
                    feature_history / len(feature_events), 1
                )
                if feature_events
                else 0.0,
            }

        return {
            # Compatibility: requests historically meant recorded model calls.
            "requests": model_calls,
            "logical_requests": logical_requests,
            "model_calls": model_calls,
            "retry_failover_calls": retry_failover_calls,
            "retry_failover_input_tokens": retry_failover_input_tokens,
            "call_amplification": round(
                model_calls / logical_requests, 3
            )
            if logical_requests
            else 0.0,
            "luna": luna_low + luna_high,
            "luna_low": luna_low,
            "luna_high": luna_high,
            # Deprecated compatibility aliases.
            "terra": luna_high,
            "sol": advanced,
            "advanced": advanced,
            "luna_rate": round(
                (luna_low + luna_high) / model_calls * 100, 1
            )
            if model_calls
            else 0.0,
            "luna_low_rate": round(luna_low / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "luna_high_rate": round(luna_high / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "terra_rate": round(luna_high / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "sol_rate": round(advanced / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "advanced_rate": round(advanced / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "input_output_ratio": round(input_tokens / output_tokens, 3)
            if output_tokens
            else 0.0,
            "avg_input_tokens": round(input_tokens / model_calls, 1)
            if model_calls
            else 0.0,
            "avg_output_tokens": round(output_tokens / model_calls, 1)
            if model_calls
            else 0.0,
            "avg_system_prompt_chars": round(
                system_prompt_chars / model_calls, 1
            )
            if model_calls
            else 0.0,
            "avg_history_chars": round(history_chars / model_calls, 1)
            if model_calls
            else 0.0,
            "avg_user_chars": round(user_chars / model_calls, 1)
            if model_calls
            else 0.0,
            "avg_estimated_input_tokens": round(
                estimated_input_tokens / model_calls, 1
            )
            if model_calls
            else 0.0,
            "avg_latency_ms": round(
                sum(latencies) / len(latencies), 1
            )
            if latencies
            else 0.0,
            "completion_rate": round(completed / model_calls * 100, 1)
            if model_calls
            else 0.0,
            "cache_rate": round(cached_tokens / input_tokens * 100, 1)
            if input_tokens
            else 0.0,
            "max_tokens_incomplete": max_tokens_incomplete,
            "same_model_max_tokens_retry": same_model_max_tokens_retry,
            "estimated_cost_units": round(
                sum(e.estimated_cost_units or 0 for e in events), 3
            ),
            "by_feature": by_feature,
        }

    def previous_month_summary(self) -> dict[str, Any]:
        now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        current_start = now_jst.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        previous_start = (current_start - timedelta(days=1)).replace(day=1)
        start_utc = previous_start.astimezone(timezone.utc)
        end_utc = current_start.astimezone(timezone.utc)
        events = [
            e
            for e in self.snapshot()
            if start_utc
            <= datetime.fromisoformat(
                e.created_at or datetime.now(timezone.utc).isoformat()
            )
            < end_utc
        ]
        input_tokens = sum(e.input_tokens for e in events)
        output_tokens = sum(e.output_tokens for e in events)
        logical_requests = len(
            {
                self._logical_key(event, index)
                for index, event in enumerate(events)
            }
        )
        return {
            "requests": len(events),
            "logical_requests": logical_requests,
            "model_calls": len(events),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    @staticmethod
    def estimate_actual_units(
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        route: str | None = None,
        reasoning_effort: str | None = None,
    ) -> float:
        # Relative units until provider pricing is explicitly configured.
        return round(
            CostPolicy.model_weight(
                model,
                route=route,
                reasoning_effort=reasoning_effort,
            )
            * (input_tokens + output_tokens)
            / 1000.0,
            3,
        )

    @staticmethod
    def month_start_utc() -> datetime:
        now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        start_jst = now_jst.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return start_jst.astimezone(timezone.utc)
