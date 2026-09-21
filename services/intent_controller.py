from __future__ import annotations

import os
from dataclasses import dataclass

from services.orchestration_context import OrchestrationContext


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    requested_pipeline: str
    effective_pipeline: str
    controller_enabled: bool
    reason: str


class IntentController:
    """Maps deterministic intent hints to orchestration pipelines.

    Phase A keeps dispatch behavior opt-in. Until explicit handlers are wired,
    unsupported or disabled pipelines remain on the general chat path.
    """

    PIPELINES = {
        "translation-like": "translation",
        "summary-like": "summarization",
        "definition-like": "definition",
        "analysis": "general-chat",
        "question": "general-chat",
        "casual-chat": "general-chat",
    }

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = (
            _env_flag("AI_INTENT_CONTROLLER", False)
            if enabled is None
            else bool(enabled)
        )

    def decide(
        self,
        context: OrchestrationContext,
        *,
        supported_pipelines: set[str] | None = None,
    ) -> IntentDecision:
        requested = self.PIPELINES.get(context.current_intent, "general-chat")
        supported = supported_pipelines or {"general-chat"}

        if not self.enabled:
            return IntentDecision(
                intent=context.current_intent,
                requested_pipeline=requested,
                effective_pipeline="general-chat",
                controller_enabled=False,
                reason="controller_disabled",
            )
        if requested not in supported:
            return IntentDecision(
                intent=context.current_intent,
                requested_pipeline=requested,
                effective_pipeline="general-chat",
                controller_enabled=True,
                reason="pipeline_not_registered",
            )
        return IntentDecision(
            intent=context.current_intent,
            requested_pipeline=requested,
            effective_pipeline=requested,
            controller_enabled=True,
            reason="intent_dispatch",
        )
