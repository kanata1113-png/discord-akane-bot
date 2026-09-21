from __future__ import annotations

from dataclasses import dataclass, replace

from config import Config
from services.routing_policy import RouteSelection


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reason: str
    score: int = 0


class SolPromotionGate:
    """Score explicit depth and structural complexity before allowing Sol.

    This is deliberately deterministic and conservative: model promotion is
    never based on a single generic word such as "詳しく" alone.
    """

    EXPLICIT = (
        "徹底的に",
        "厳密に",
        "深掘り",
        "複数の観点",
        "多角的に",
        "体系的に",
        "詳細に分析",
    )
    COMPLEX = (
        "比較", "反論", "複数", "制約", "判例", "根拠", "トレードオフ",
        "前提", "例外", "因果", "シナリオ",
    )

    @classmethod
    def score(cls, content: str) -> int:
        text = (content or "").strip()
        explicit_hits = sum(1 for marker in cls.EXPLICIT if marker in text)
        complexity_hits = sum(1 for marker in cls.COMPLEX if marker in text)
        score = explicit_hits * 2 + min(complexity_hits, 3)
        if len(text) >= 120:
            score += 1
        if len(text) >= 400:
            score += 1
        return score

    @classmethod
    def apply(cls, selection: RouteSelection, content: str) -> tuple[RouteSelection, PromotionDecision]:
        if selection.model != Config.REASONING_MODEL:
            return selection, PromotionDecision(False, "not_sol_candidate", 0)

        score = cls.score(content)
        if score >= 3:
            return selection, PromotionDecision(True, "deep_complexity_score", score)

        return replace(
            selection,
            model=Config.CHAT_MODEL,
            reasoning_effort=Config.CHAT_REASONING_EFFORT,
            route="reasoning",
            max_output_tokens=min(selection.max_output_tokens, Config.REASONING_MAX_TOKENS),
            fallback_reason="sol_promotion_gate_demote",
        ), PromotionDecision(False, "insufficient_sol_score", score)
