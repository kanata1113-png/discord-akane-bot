from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any


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

    @staticmethod
    def new_event_id() -> str:
        return uuid.uuid4().hex[:12]

    def emit(self, metric: RoutingMetric) -> None:
        logger.info(
            "ROUTING_METRIC %s",
            json.dumps(
                metric.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
