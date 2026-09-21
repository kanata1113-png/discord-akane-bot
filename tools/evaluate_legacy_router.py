#!/usr/bin/env python3
"""Offline characterization suite for deterministic routing behavior.

This does not call Jev or OpenAI. It provides a stable baseline that future
router providers can be compared against.
"""

from __future__ import annotations

from collections import Counter

from services.routing_policy import RoutingPolicy


CASES = [
    ("こんにちは", "normal-chat"),
    ("今日の調子どう？", "normal-chat"),
    ("この言葉の意味を簡単に教えて", "normal-chat"),
    ("メリットとデメリットを比較して", "reasoning"),
    ("原因と結果を分析して", "reasoning"),
    ("複数の観点から考えて", "reasoning"),
    ("表現の自由について教えて", "regulation"),
    ("検閲の問題点を説明して", "regulation"),
    ("体系的に深く分析して", "deep-reasoning"),
    ("徹底的に多角的に検討して", "deep-reasoning"),
]


def main() -> int:
    results = []
    for text, expected in CASES:
        actual = RoutingPolicy.legacy_route(text)
        results.append((text, expected, actual, expected == actual))

    passed = sum(ok for _, _, _, ok in results)
    counts = Counter(actual for _, _, actual, _ in results)

    print(f"cases: {len(results)}")
    print(f"passed: {passed}/{len(results)}")
    print("route counts:", dict(counts))
    for text, expected, actual, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status} expected={expected} actual={actual} text={text}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
