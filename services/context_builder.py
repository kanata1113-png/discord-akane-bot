from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


FOLLOWUP_MARKERS = (
    "それ",
    "これ",
    "さっき",
    "前の",
    "もう少し",
    "続けて",
    "その点",
    "その話",
    "その件",
    "that",
    "this",
    "previous",
    "more detail",
    "continue",
)


@dataclass(frozen=True)
class RoutingContext:
    """Privacy-minimal conversation metadata for model routing.

    Prior message bodies are never included in the hint. When the current
    message looks like a true follow-up, locally-derived metadata about the
    recent conversation anchor can be attached to preserve routing continuity.
    """

    history_messages: int
    prior_user_messages: int
    prior_assistant_messages: int
    followup_like: bool
    previous_route: str | None = None
    previous_intent: str | None = None

    def as_hint(self) -> str:
        parts = [
            f"history:{self.history_messages}",
            f"prior_user:{self.prior_user_messages}",
            f"prior_assistant:{self.prior_assistant_messages}",
            f"followup:{str(self.followup_like).lower()}",
        ]
        if self.followup_like and self.previous_route:
            parts.append(f"previous_route:{self.previous_route}")
        if self.followup_like and self.previous_intent:
            parts.append(f"previous_intent:{self.previous_intent}")
        return "routing_context=" + ",".join(parts)


class ContextBuilder:
    @staticmethod
    def looks_like_followup(content: str, *, has_history: bool = True) -> bool:
        if not has_history:
            return False
        text = (content or "").strip().lower()
        return any(marker.lower() in text for marker in FOLLOWUP_MARKERS)

    @staticmethod
    def build(
        content: str,
        history: Iterable[Mapping[str, object]] | None,
        *,
        previous_route: str | None = None,
        previous_intent: str | None = None,
    ) -> RoutingContext:
        usable = []
        for item in history or []:
            role = item.get("role")
            body = item.get("content")
            if role in {"user", "assistant"} and isinstance(body, str) and body:
                usable.append(role)

        followup_like = ContextBuilder.looks_like_followup(
            content,
            has_history=bool(usable),
        )

        return RoutingContext(
            history_messages=len(usable),
            prior_user_messages=sum(role == "user" for role in usable),
            prior_assistant_messages=sum(role == "assistant" for role in usable),
            followup_like=followup_like,
            previous_route=previous_route if followup_like else None,
            previous_intent=previous_intent if followup_like else None,
        )
