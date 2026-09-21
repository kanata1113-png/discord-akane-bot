from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


FOLLOWUP_MARKERS = (
    "それ",
    "これ",
    "さっき",
    "前の",
    "もう少し",
    "詳しく",
    "比較して",
    "続けて",
    "その点",
    "that",
    "this",
    "previous",
    "more detail",
    "continue",
)


@dataclass(frozen=True)
class RoutingContext:
    """Privacy-minimal conversation metadata for model routing.

    No prior message body is returned. The context only describes whether the
    current message looks like a follow-up and how much usable history exists.
    """

    history_messages: int
    prior_user_messages: int
    prior_assistant_messages: int
    followup_like: bool

    def as_hint(self) -> str:
        return (
            "routing_context="
            f"history:{self.history_messages},"
            f"prior_user:{self.prior_user_messages},"
            f"prior_assistant:{self.prior_assistant_messages},"
            f"followup:{str(self.followup_like).lower()}"
        )


class ContextBuilder:
    @staticmethod
    def build(
        content: str,
        history: Iterable[Mapping[str, object]] | None,
    ) -> RoutingContext:
        usable = []
        for item in history or []:
            role = item.get("role")
            body = item.get("content")
            if role in {"user", "assistant"} and isinstance(body, str) and body:
                usable.append(role)

        text = (content or "").strip().lower()
        followup_like = bool(usable) and any(
            marker.lower() in text for marker in FOLLOWUP_MARKERS
        )

        return RoutingContext(
            history_messages=len(usable),
            prior_user_messages=sum(role == "user" for role in usable),
            prior_assistant_messages=sum(role == "assistant" for role in usable),
            followup_like=followup_like,
        )
