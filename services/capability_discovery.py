from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from services.capability_core import CapabilitySpec


ACTION_MARKERS = (
    "見たい",
    "確認",
    "教えて",
    "表示",
    "ランキング",
    "順位",
    "レベル",
    "xp",
    "プロフィール",
    "実績",
    "運勢",
    "占い",
    "rank",
    "level",
    "profile",
    "achievement",
    "fortune",
)

QUESTION_PREFIXES = (
    "どう思う",
    "なぜ",
    "なんで",
    "理由",
    "分析",
    "比較して",
)


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    capability_id: str
    name: str
    description: str
    slash_command: str | None
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryDecision:
    should_route: bool
    candidates: tuple[DiscoveryCandidate, ...]
    reason: str


def should_attempt_discovery(content: str) -> bool:
    """Cheap local gate. False means ordinary chat continues unchanged."""

    text = (content or "").strip().lower()
    if not text or len(text) > 180:
        return False
    if any(text.startswith(prefix) for prefix in QUESTION_PREFIXES):
        return False
    return any(marker in text for marker in ACTION_MARKERS)


def shortlist_capabilities(
    content: str,
    specs: Iterable[CapabilitySpec],
    *,
    limit: int = 4,
) -> tuple[DiscoveryCandidate, ...]:
    """Rank discoverable capabilities locally before any optional Jev call."""

    text = (content or "").strip().lower()
    ranked: list[DiscoveryCandidate] = []

    for spec in specs:
        if not spec.discoverable:
            continue

        terms = tuple(
            dict.fromkeys(
                term.strip().lower()
                for term in (
                    spec.capability_id,
                    spec.name,
                    *spec.tags,
                )
                if term and term.strip()
            )
        )
        matched = tuple(term for term in terms if term in text)
        if not matched:
            continue

        score = sum(
            3.0 if term == spec.capability_id else 2.0
            for term in matched
        )
        if spec.name.lower() in text:
            score += 2.0
        if spec.capability_id == "weekly" and (
            "今週" in text or "週間" in text
        ):
            score += 3.0

        ranked.append(
            DiscoveryCandidate(
                capability_id=spec.capability_id,
                name=spec.name,
                description=spec.description,
                slash_command=spec.slash_command,
                score=score,
                matched_terms=matched,
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.capability_id))
    return tuple(ranked[:limit])


def discover_locally(
    content: str,
    specs: Iterable[CapabilitySpec],
    *,
    limit: int = 4,
) -> DiscoveryDecision:
    if not should_attempt_discovery(content):
        return DiscoveryDecision(False, (), "gate_rejected")

    candidates = shortlist_capabilities(content, specs, limit=limit)
    if not candidates:
        return DiscoveryDecision(False, (), "no_local_candidate")

    return DiscoveryDecision(True, candidates, "local_candidate")
