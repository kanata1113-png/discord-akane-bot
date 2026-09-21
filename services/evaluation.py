from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from services.routing_policy import RoutingPolicy


@dataclass(frozen=True)
class RoutingBenchmarkCase:
    """Explicit, user-owned benchmark case.

    Prompt text is intentionally kept out of production routing telemetry. This
    type is for offline fixtures supplied in-repository or by an operator.
    """

    case_id: str
    content: str
    expected_route: str
    history: Sequence[Mapping[str, object]] = ()


@dataclass(frozen=True)
class RoutingBenchmarkResult:
    case_id: str
    expected_route: str
    selected_route: str
    source: str
    matched: bool


@dataclass(frozen=True)
class TelemetryReplayEvent:
    """Privacy-safe representation of a ROUTING_METRIC event.

    It can be analyzed and aggregated, but cannot reproduce routing because the
    original message body is deliberately absent from production telemetry.
    """

    event_id: str | None
    selected_route: str
    legacy_route: str
    jev_route: str | None
    confidence: float | None
    fallback_reason: str | None
    followup_like: bool | None
    previous_route: str | None
    intent_hint: str | None
    model: str | None
    latency_ms: int | None

    @classmethod
    def from_mapping(cls, item: Mapping[str, object]) -> "TelemetryReplayEvent":
        return cls(
            event_id=_optional_str(item.get("event_id")),
            selected_route=str(item.get("selected_route") or ""),
            legacy_route=str(item.get("legacy_route") or ""),
            jev_route=_optional_str(item.get("jev_route")),
            confidence=_optional_float(item.get("confidence")),
            fallback_reason=_optional_str(item.get("fallback_reason")),
            followup_like=_optional_bool(item.get("followup_like")),
            previous_route=_optional_str(item.get("previous_route")),
            intent_hint=_optional_str(item.get("intent_hint")),
            model=_optional_str(item.get("model")),
            latency_ms=_optional_int(item.get("latency_ms")),
        )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


async def evaluate_routing_cases(
    policy: RoutingPolicy,
    cases: Iterable[RoutingBenchmarkCase],
) -> list[RoutingBenchmarkResult]:
    results: list[RoutingBenchmarkResult] = []
    for case in cases:
        selection = await policy.select(case.content, history=list(case.history))
        results.append(
            RoutingBenchmarkResult(
                case_id=case.case_id,
                expected_route=case.expected_route,
                selected_route=selection.route,
                source=selection.source,
                matched=selection.route == case.expected_route,
            )
        )
    return results


def summarize_telemetry(events: Iterable[TelemetryReplayEvent]) -> dict[str, object]:
    items = list(events)
    if not items:
        return {
            "events": 0,
            "fallbacks": 0,
            "followups": 0,
            "mean_confidence": None,
            "mean_latency_ms": None,
        }

    confidences = [x.confidence for x in items if x.confidence is not None]
    latencies = [x.latency_ms for x in items if x.latency_ms is not None]
    return {
        "events": len(items),
        "fallbacks": sum(bool(x.fallback_reason) for x in items),
        "followups": sum(x.followup_like is True for x in items),
        "mean_confidence": (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        ),
        "mean_latency_ms": (
            round(sum(latencies) / len(latencies), 1) if latencies else None
        ),
    }
