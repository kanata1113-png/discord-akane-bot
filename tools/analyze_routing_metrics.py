#!/usr/bin/env python3
"""Summarize privacy-minimal ROUTING_METRIC log lines.

Usage:
    python tools/analyze_routing_metrics.py railway.log

The input is expected to contain normal application logs with embedded lines of
`ROUTING_METRIC {json}`. Message content and Discord identifiers are not needed.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path


PREFIX = "ROUTING_METRIC "


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
    if not total:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: analyze_routing_metrics.py <logfile>")
        return 2

    path = Path(sys.argv[1])
    metrics = load_metrics(path)
    decisions = [
        item for item in metrics
        if item.get("event") == "routing_decision"
    ]
    shadows = [
        item for item in metrics
        if item.get("event") == "shadow_observation"
    ]

    sources = Counter(item.get("source", "unknown") for item in decisions)
    selected = Counter(
        item.get("selected_route", "unknown") for item in decisions
    )
    fallbacks = Counter(
        item.get("fallback_reason")
        for item in decisions
        if item.get("fallback_reason")
    )
    latencies = [
        int(item["latency_ms"])
        for item in metrics
        if item.get("latency_ms") is not None
    ]
    confidences = [
        float(item["confidence"])
        for item in metrics
        if item.get("confidence") is not None
    ]

    print(f"routing decisions: {len(decisions)}")
    print(f"shadow observations: {len(shadows)}")
    print(
        "jev source: "
        f"{sources.get('jev', 0)} "
        f"({pct(sources.get('jev', 0), len(decisions))})"
    )
    print(
        "legacy source: "
        f"{sources.get('legacy', 0)} "
        f"({pct(sources.get('legacy', 0), len(decisions))})"
    )
    print("selected routes:", dict(selected))
    print("fallback reasons:", dict(fallbacks))

    if latencies:
        print(f"jev latency mean ms: {statistics.mean(latencies):.1f}")
        print(f"jev latency median ms: {statistics.median(latencies):.1f}")
        print(f"jev latency max ms: {max(latencies)}")

    if confidences:
        print(f"confidence mean: {statistics.mean(confidences):.4f}")
        print(f"confidence min: {min(confidences):.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
