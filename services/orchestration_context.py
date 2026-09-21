from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from config import Config
from services.context_builder import ContextBuilder
from services.intent_gate import IntentGate


FORMAT_MARKERS = {
    "bullets": ("箇条書き", "bullet", "bullets"),
    "table": ("表に", "表形式", "table"),
    "code": ("コード", "code", "実装例"),
    "short": ("簡潔", "短く", "brief", "concise"),
    "detailed": ("詳しく", "詳細", "deeply", "in detail"),
}


@dataclass(frozen=True)
class ExternalRoutingContext:
    """Privacy-minimal routing metadata safe to expose to an external router."""

    history_messages: int
    prior_user_messages: int
    prior_assistant_messages: int
    followup_like: bool
    previous_route: str | None
    previous_intent: str | None
    current_intent: str
    message_length: int
    requested_format: str | None

    def as_hint(self) -> str:
        parts = [
            f"history:{self.history_messages}",
            f"prior_user:{self.prior_user_messages}",
            f"prior_assistant:{self.prior_assistant_messages}",
            f"followup:{str(self.followup_like).lower()}",
            f"current_intent:{self.current_intent}",
            f"message_length:{self.message_length}",
        ]
        if self.followup_like and self.previous_route:
            parts.append(f"previous_route:{self.previous_route}")
        if self.followup_like and self.previous_intent:
            parts.append(f"previous_intent:{self.previous_intent}")
        if self.requested_format:
            parts.append(f"requested_format:{self.requested_format}")
        return "routing_context=" + ",".join(parts)


@dataclass(frozen=True)
class OrchestrationContext:
    """Local request context used by the orchestration control plane.

    `content` is deliberately local-only. `external` contains the restricted
    metadata projection that may be sent to external routing providers.
    """

    content: str
    current_intent: str
    regulation_mode: bool
    requested_format: str | None
    message_length: int
    external: ExternalRoutingContext


class OrchestrationContextBuilder:
    @staticmethod
    def requested_format(content: str) -> str | None:
        text = (content or "").strip().lower()
        for name, markers in FORMAT_MARKERS.items():
            if any(marker.lower() in text for marker in markers):
                return name
        return None

    @classmethod
    def build(
        cls,
        content: str,
        history: Iterable[Mapping[str, object]] | None,
        *,
        previous_route: str | None = None,
        previous_intent: str | None = None,
    ) -> OrchestrationContext:
        base = ContextBuilder.build(
            content,
            history,
            previous_route=previous_route,
            previous_intent=previous_intent,
        )
        current_intent = IntentGate.classify(content)
        requested_format = cls.requested_format(content)
        text = (content or "").strip()
        external = ExternalRoutingContext(
            history_messages=base.history_messages,
            prior_user_messages=base.prior_user_messages,
            prior_assistant_messages=base.prior_assistant_messages,
            followup_like=base.followup_like,
            previous_route=base.previous_route,
            previous_intent=base.previous_intent,
            current_intent=current_intent,
            message_length=len(text),
            requested_format=requested_format,
        )
        return OrchestrationContext(
            content=text,
            current_intent=current_intent,
            regulation_mode=any(keyword in text for keyword in Config.REGULATION_KEYWORDS),
            requested_format=requested_format,
            message_length=len(text),
            external=external,
        )
