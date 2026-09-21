from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityCostCase:
    expected_model: str
    actual_model: str
    completed: bool
    latency_ms: int
    cost_units: float
    human_quality: float | None = None


@dataclass(frozen=True)
class QualityCostResult:
    route_match: bool
    completion_score: float
    human_quality: float | None
    latency_ms: int
    cost_units: float


def evaluate(case: QualityCostCase) -> QualityCostResult:
    """Return transparent components instead of inventing a single magic score.

    Human quality remains optional and is never inferred from cost or latency.
    This keeps benchmark decisions auditable and prevents cheap-but-bad answers
    from being treated as automatically superior.
    """
    return QualityCostResult(
        route_match=case.expected_model == case.actual_model,
        completion_score=1.0 if case.completed else 0.0,
        human_quality=case.human_quality,
        latency_ms=max(0, int(case.latency_ms)),
        cost_units=max(0.0, float(case.cost_units)),
    )
