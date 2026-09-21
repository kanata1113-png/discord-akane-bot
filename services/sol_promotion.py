from __future__ import annotations

from dataclasses import dataclass, replace

from config import Config
from services.routing_policy import RouteSelection


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reason: str


class SolPromotionGate:
    """Require explicit deep-complexity evidence before allowing Sol."""

    EXPLICIT = (
        "徹底的に",
        "厳密に",
        "深掘り",
        "複数の観点",
        "多角的に",
        "体系的に",
        "詳細に分析",
    )
    COMPLEX = ("比較", "反論", "複数", "制約", "判例", "根拠", "トレードオフ")

    @classmethod
    def apply(cls, selection: RouteSelection, content: str) -> tuple[RouteSelection, PromotionDecision]:
        if selection.model != Config.REASONING_MODEL:
            return selection, PromotionDecision(False, "not_sol_candidate")

        text = (content or "").strip()
        explicit_hits = sum(1 for marker in cls.EXPLICIT if marker in text)
        complexity_hits = sum(1 for marker in cls.COMPLEX if marker in text)

        if explicit_hits >= 2 or (
            explicit_hits >= 1 and (complexity_hits >= 1 or len(text) >= 120)
        ):
            return selection, PromotionDecision(True, "explicit_deep_complexity")

        return replace(
            selection,
            model=Config.CHAT_MODEL,
            reasoning_effort=Config.CHAT_REASONING_EFFORT,
            route="reasoning",
            max_output_tokens=min(selection.max_output_tokens, Config.REASONING_MAX_TOKENS),
            fallback_reason="sol_promotion_gate_demote",
        ), PromotionDecision(False, "insufficient_sol_evidence")
