#!/usr/bin/env python3
"""Summarize privacy-minimal ROUTING_METRIC log lines.

Usage:
    python tools/analyze_routing_metrics.py railway.log

No message content or Discord identity is required.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path


PREFIX = "ROUTING_METRIC "
CONFIDENCE_BUCKETS = ((0.0, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 0.95), (0.95, 1.01))


def load_metrics(path: Path) -> list[dict]:
    metrics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        marker = line.find(PREFIX)
        if marker < 0:
            continue
        payload = line[marker + len(PREFIX):].strip()
        try:
            metrics.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return metrics


def pct(part: int, total: int) -> str:
    return "0.0%" if not total else f"{part / total * 100:.1f}%"


def confidence_bucket(value: float) -> str:
    for low, high in CONFIDENCE_BUCKETS:
        if low <= value < high:
            return f"{low:.2f}-{min(high, 1.0):.2f}"
    return "unknown"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: analyze_routing_metrics.py <logfile>")
        return 2

    metrics = load_metrics(Path(sys.argv[1]))
    decisions = [m for m in metrics if m.get("event") == "routing_decision"]
    shadows = [m for m in metrics if m.get("event") == "shadow_observation"]

    sources = Counter(m.get("source", "unknown") for m in decisions)
    selected = Counter(m.get("selected_route", "unknown") for m in decisions)
    models = Counter(m.get("model", "unknown") for m in decisions)
    intents = Counter(m.get("intent_hint", "unknown") for m in decisions)
    budgets = Counter(m.get("budget_reason", "fixed") for m in decisions)
    fallbacks = Counter(m.get("fallback_reason") for m in decisions if m.get("fallback_reason"))

    disagreements = [
        m for m in metrics
        if m.get("jev_route") and m.get("legacy_route") and m.get("jev_route") != m.get("legacy_route")
    ]
    promotions = [
        m for m in disagreements
        if m.get("legacy_route") == "normal-chat" and m.get("jev_route") in {"reasoning", "deep-reasoning"}
    ]
    demotions = [
        m for m in disagreements
        if m.get("legacy_route") in {"reasoning", "deep-reasoning"} and m.get("jev_route") == "normal-chat"
    ]

    latencies = [int(m["latency_ms"]) for m in metrics if m.get("latency_ms") is not None]
    confidences = [float(m["confidence"]) for m in metrics if m.get("confidence") is not None]
    confidence_counts = Counter(confidence_bucket(v) for v in confidences)
    relative_costs = [float(m["estimated_cost_units"]) for m in decisions if m.get("estimated_cost_units") is not None]
    followups = sum(bool(m.get("followup_like")) for m in decisions)

    print(f"routing decisions: {len(decisions)}")
    print(f"shadow observations: {len(shadows)}")
    print(f"jev source: {sources.get('jev', 0)} ({pct(sources.get('jev', 0), len(decisions))})")
    print(f"legacy source: {sources.get('legacy', 0)} ({pct(sources.get('legacy', 0), len(decisions))})")
    print(f"jev/legacy disagreements: {len(disagreements)} ({pct(len(disagreements), len(metrics))})")
    print(f"promotions normal->reasoning/deep: {len(promotions)}")
    print(f"demotions reasoning/deep->normal: {len(demotions)}")
    print(f"follow-up-like decisions: {followups}")
    print("selected routes:", dict(selected))
    print("models:", dict(models))
    print("intent hints:", dict(intents))
    print("fallback reasons:", dict(fallbacks))
    print("confidence buckets:", dict(confidence_counts))
    print("budget reasons:", dict(budgets))

    if relative_costs:
        print(f"relative cost units total: {sum(relative_costs):.3f}")
        print(f"relative cost units mean: {statistics.mean(relative_costs):.3f}")

    if latencies:
        ordered = sorted(latencies)
        p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
        print(f"jev latency mean ms: {statistics.mean(latencies):.1f}")
        print(f"jev latency median ms: {statistics.median(latencies):.1f}")
        print(f"jev latency p95-ish ms: {ordered[p95_index]}")
        print(f"jev latency max ms: {max(latencies)}")

    if confidences:
        print(f"confidence mean: {statistics.mean(confidences):.4f}")
        print(f"confidence min: {min(confidences):.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
