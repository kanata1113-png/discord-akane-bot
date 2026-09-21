from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from services.capability_core import CapabilitySpec


ACTION_VERBS = (
    "見たい",
    "確認",
    "表示",
    "見せて",
    "知りたい",
    "占いたい",
    "して",
    "してほしい",
    "使いたい",
    "調べたい",
)

CAPABILITY_MARKERS = (
    "ランキング",
    "順位",
    "レベル",
    "xp",
    "プロフィール",
    "実績",
    "運勢",
    "占い",
    "称号",
    "メモリー",
    "記憶",
    "翻訳",
    "要約",
    "辞書",
    "rank",
    "level",
    "profile",
    "achievement",
    "fortune",
    "title",
    "memory",
    "translate",
    "summary",
    "define",
)

CHAT_INTENT_MARKERS = (
    "どう思う",
    "なぜ",
    "なんで",
    "理由",
    "分析",
    "比較して",
    "意味",
    "とは",
    "について",
    "教えて",
)

TITLE_WRITE_MARKERS = (
    "変更",
    "変えて",
    "設定",
    "装備",
    "つけて",
)

MEMORY_DELETE_MARKERS = (
    "消して",
    "削除",
    "忘れて",
    "忘れ",
    "clear",
    "delete",
    "forget",
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


def _has_unsupported_write_intent(text: str) -> bool:
    """Reject write-shaped intents not yet approved for discovery.

    Release C intentionally exposes read/AI candidates before WRITE_CONFIRM
    capabilities. Without this local guard, phrases such as "称号を変更して"
    could incorrectly surface the read-only titles candidate, or "記憶を消して"
    could surface memory status. Those requests must stay outside discovery until
    a dedicated confirmation UX is implemented.
    """

    has_title_subject = any(
        marker in text for marker in ("称号", "title")
    )
    if has_title_subject and any(marker in text for marker in TITLE_WRITE_MARKERS):
        return True

    has_memory_subject = any(
        marker in text for marker in ("メモリー", "記憶", "memory")
    )
    if has_memory_subject and any(marker in text for marker in MEMORY_DELETE_MARKERS):
        return True

    return False


def should_attempt_discovery(content: str) -> bool:
    """Cheap local gate. False means ordinary chat continues unchanged."""

    text = (content or "").strip().lower()
    if not text or len(text) > 180:
        return False
    if any(marker in text for marker in CHAT_INTENT_MARKERS):
        return False
    if _has_unsupported_write_intent(text):
        return False

    has_capability = any(
        marker in text for marker in CAPABILITY_MARKERS
    )
    has_action = any(
        marker in text for marker in ACTION_VERBS
    )
    return has_capability and has_action


def shortlist_capabilities(
    content: str,
    specs: Iterable[CapabilitySpec],
    *,
    limit: int = 4,
) -> tuple[DiscoveryCandidate, ...]:
    """Rank discoverable capabilities locally before any optional Jev call."""

    text = (content or "").strip().lower()
    ranked: list[DiscoveryCandidate] = []

    aliases = {
        "level": ("レベル",),
        "leaderboard": ("レベルランキング",),
        "achievements": ("実績",),
        "fortune": ("運勢", "占い"),
        "profile": ("プロフィール",),
        "titles": ("称号",),
        "memory_status": ("メモリー", "記憶"),
        "translate": ("翻訳",),
        "summary": ("要約",),
        "define": ("辞書",),
    }

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
        semantic_matches = [
            alias
            for alias in aliases.get(spec.capability_id, ())
            if alias in text
        ]
        if (
            spec.capability_id == "rankings"
            and ("ランキング" in text or "順位" in text)
        ):
            semantic_matches.append("ランキング")
        matched = tuple(dict.fromkeys((*matched, *semantic_matches)))
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
        if spec.capability_id == "leaderboard" and "レベル" in text:
            score += 2.0

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
