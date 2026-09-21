#!/usr/bin/env python3
"""Evaluate Jev confidence thresholds against human route labels.

Usage:
    python tools/calibrate_routing_thresholds.py railway.log labels.csv

labels.csv columns:
    event_id,human_preferred_route

No message content is required. The tool does not modify production settings.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from tools.analyze_routing_metrics import load_metrics


THRESHOLDS = (0.80, 0.85, 0.90, 0.95)


def load_labels(path: Path) -> dict[str, str]:
    labels = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            event_id = (row.get("event_id") or "").strip()
            route = (row.get("human_preferred_route") or "").strip()
            if event_id and route:
                labels[event_id] = route
    return labels


def evaluate(metrics: list[dict], labels: dict[str, str], threshold: float) -> dict[str, int | float]:
    labeled = 0
    jev_used = 0
    correct = 0
    fallback_correct = 0

    for metric in metrics:
        event_id = metric.get("event_id")
        human = labels.get(event_id)
        if not human or not metric.get("jev_route"):
            continue

        labeled += 1
        confidence = float(metric.get("confidence") or 0.0)
        if confidence >= threshold:
            chosen = metric.get("jev_route")
            jev_used += 1
        else:
            chosen = metric.get("legacy_route")
            if chosen == human:
                fallback_correct += 1

        if chosen == human:
            correct += 1

    accuracy = (correct / labeled) if labeled else 0.0
    jev_rate = (jev_used / labeled) if labeled else 0.0
    return {
        "labeled": labeled,
        "correct": correct,
        "accuracy": accuracy,
        "jev_used": jev_used,
        "jev_rate": jev_rate,
        "fallback_correct": fallback_correct,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: calibrate_routing_thresholds.py <logfile> <labels.csv>")
        return 2

    metrics = [
        item for item in load_metrics(Path(sys.argv[1]))
        if item.get("event") == "routing_decision"
    ]
    labels = load_labels(Path(sys.argv[2]))

    print(f"labels loaded: {len(labels)}")
    for threshold in THRESHOLDS:
        result = evaluate(metrics, labels, threshold)
        print(
            f"threshold={threshold:.2f} "
            f"labeled={result['labeled']} "
            f"accuracy={result['accuracy']:.3f} "
            f"jev_rate={result['jev_rate']:.3f} "
            f"fallback_correct={result['fallback_correct']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
