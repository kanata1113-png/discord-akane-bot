from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetailDecision:
    level: str
    reason: str


class DetailIntent:
    """Deterministic answer-detail detector independent of model routing."""

    COMPACT = ("簡潔", "短く", "要点だけ", "一言で", "手短に", "brief", "concise")
    EXPANDED = ("詳しく", "詳細", "深掘り", "徹底的", "できるだけ詳しく", "in detail", "deeply")

    @classmethod
    def classify(cls, content: str) -> DetailDecision:
        text = (content or "").strip().lower()
        if any(marker.lower() in text for marker in cls.COMPACT):
            return DetailDecision("compact", "explicit_compact")
        if any(marker.lower() in text for marker in cls.EXPANDED):
            return DetailDecision("expanded", "explicit_expanded")
        return DetailDecision("default", "default")
