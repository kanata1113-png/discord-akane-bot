from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CalibrationObservation:
    confidence: float
    accepted: bool
    route_correct: bool


@dataclass(frozen=True)
class ThresholdReport:
    threshold: float
    accepted: int
    correct: int
    precision: float
    coverage: float


def evaluate_threshold(
    observations: Iterable[CalibrationObservation],
    threshold: float,
) -> ThresholdReport:
    rows = list(observations)
    accepted_rows = [row for row in rows if row.accepted and row.confidence >= threshold]
    correct = sum(row.route_correct for row in accepted_rows)
    accepted = len(accepted_rows)
    precision = correct / accepted if accepted else 0.0
    coverage = accepted / len(rows) if rows else 0.0
    return ThresholdReport(
        threshold=threshold,
        accepted=accepted,
        correct=correct,
        precision=round(precision, 4),
        coverage=round(coverage, 4),
    )


def compare_thresholds(
    observations: Iterable[CalibrationObservation],
    thresholds: Iterable[float] = (0.80, 0.82, 0.85, 0.88, 0.90),
) -> list[ThresholdReport]:
    rows = list(observations)
    return [evaluate_threshold(rows, threshold) for threshold in thresholds]
