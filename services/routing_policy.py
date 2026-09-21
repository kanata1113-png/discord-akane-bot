from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, replace

from config import Config
from services.context_builder import ContextBuilder, RoutingContext
from services.jev_model_router import JevModelRouter, JevRouteDecision
from services.routing_metrics import RoutingMetric, RoutingTelemetry
from services.token_budget import TokenBudgetPolicy


logger = logging.getLogger("AkaneBot")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ModelTier:
    model: str
    reasoning_effort: str
    max_output_tokens: int


@dataclass(frozen=True)
class RouteSelection:
    model: str
    reasoning_effort: str
    route: str
    max_output_tokens: int
    mode: str
    source: str
    legacy_route: str
    jev_route: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    fallback_reason: str | None = None
    budget_reason: str | None = None
    event_id: str | None = None
    history_messages: int | None = None
    followup_like: bool | None = None


class RoutingPolicy:
    """Single chat-routing policy with safe Legacy fallback.

    v1.3 context hints and v1.6 adaptive token budgets are opt-in flags so the
    v1.0 production behavior remains the default when this code is merged.
    """

    def __init__(
        self,
        jev_router: JevModelRouter,
        telemetry: RoutingTelemetry | None = None,
    ) -> None:
        self.jev_router = jev_router
        self.telemetry = telemetry or RoutingTelemetry()
        self._shadow_tasks: set[asyncio.Task] = set()
        self.context_hints_enabled = _env_flag("JEV_ROUTER_CONTEXT_HINTS", False)
        self.adaptive_budget_enabled = _env_flag("AI_ADAPTIVE_TOKEN_BUDGET", False)

    @staticmethod
    def tier_for_route(route: str) -> ModelTier:
        if route == "deep-reasoning":
            return ModelTier(Config.REASONING_MODEL, Config.DEEP_REASONING_EFFORT, Config.DEEP_REASONING_MAX_TOKENS)
        if route in {"reasoning", "regulation", "long-question"}:
            return ModelTier(Config.REASONING_MODEL, Config.REASONING_EFFORT, Config.REASONING_MAX_TOKENS)
        return ModelTier(Config.CHAT_MODEL, Config.CHAT_REASONING_EFFORT, Config.NORMAL_CHAT_MAX_TOKENS)

    @staticmethod
    def normalize_legacy_route(route: str) -> str:
        if route == "deep-reasoning":
            return "deep-reasoning"
        if route in {"regulation", "reasoning", "long-question"}:
            return "reasoning"
        return "normal-chat"

    @staticmethod
    def legacy_route(content: str) -> str:
        text = (content or "").strip()
        if any(keyword in text for keyword in Config.DEEP_REASONING_KEYWORDS):
            return "deep-reasoning"
        if any(keyword in text for keyword in Config.REGULATION_KEYWORDS):
            return "regulation"
        if any(keyword in text for keyword in Config.REASONING_KEYWORDS):
            return "reasoning"
        if len(text) >= 350:
            return "long-question"
        return "normal-chat"

    @classmethod
    def legacy_selection(cls, content: str) -> RouteSelection:
        route = cls.legacy_route(content)
        tier = cls.tier_for_route(route)
        return RouteSelection(
            model=tier.model,
            reasoning_effort=tier.reasoning_effort,
            route=route,
            max_output_tokens=tier.max_output_tokens,
            mode="legacy",
            source="legacy",
            legacy_route=route,
        )

    @staticmethod
    def fallback_reason(decision: JevRouteDecision) -> str:
        if decision.error:
            return decision.error
        if not decision.accepted:
            return "low_confidence"
        return "unknown"

    def _with_budget(self, selection: RouteSelection, content: str) -> RouteSelection:
        if not self.adaptive_budget_enabled:
            return selection
        budget = TokenBudgetPolicy.for_request(selection.route, content)
        return replace(
            selection,
            max_output_tokens=budget.max_output_tokens,
            budget_reason=budget.reason,
        )

    def _routing_input(
        self,
        content: str,
        context: RoutingContext | None,
    ) -> str:
        if not self.context_hints_enabled or context is None:
            return content
        return f"{content}\n\n[{context.as_hint()}]"

    def _emit(self, selection: RouteSelection) -> None:
        self.telemetry.emit(
            RoutingMetric(
                mode=selection.mode,
                source=selection.source,
                legacy_route=self.normalize_legacy_route(selection.legacy_route),
                selected_route=selection.route,
                jev_route=selection.jev_route,
                confidence=selection.confidence,
                latency_ms=selection.latency_ms,
                fallback_reason=selection.fallback_reason,
                model=selection.model,
                reasoning_effort=selection.reasoning_effort,
                max_output_tokens=selection.max_output_tokens,
                budget_reason=selection.budget_reason,
                history_messages=selection.history_messages,
                followup_like=selection.followup_like,
                event_id=selection.event_id,
            )
        )

    async def _observe_shadow(
        self,
        content: str,
        legacy: RouteSelection,
        context: RoutingContext | None = None,
    ) -> None:
        if not self.jev_router.is_configured:
            return
        decision = await self.jev_router.route(self._routing_input(content, context))
        selected = replace(
            legacy,
            mode="shadow",
            jev_route=decision.route,
            confidence=decision.confidence,
            latency_ms=decision.latency_ms,
            fallback_reason=None if decision.accepted else self.fallback_reason(decision),
            event_id=self.telemetry.new_event_id(),
            history_messages=context.history_messages if context else None,
            followup_like=context.followup_like if context else None,
        )
        self._emit(selected)

    def _schedule_shadow(
        self,
        content: str,
        legacy: RouteSelection,
        context: RoutingContext | None = None,
    ) -> None:
        if not self.jev_router.is_configured:
            return
        task = asyncio.create_task(self._observe_shadow(content, legacy, context))
        self._shadow_tasks.add(task)
        task.add_done_callback(self._shadow_tasks.discard)

    async def select(self, content: str, history=None) -> RouteSelection:
        context = ContextBuilder.build(content, history)
        legacy = self.legacy_selection(content)
        mode = getattr(self.jev_router, "mode", "legacy")
        event_id = self.telemetry.new_event_id()
        context_fields = {
            "history_messages": context.history_messages,
            "followup_like": context.followup_like,
            "event_id": event_id,
        }

        if mode == "legacy":
            selected = replace(legacy, mode="legacy", **context_fields)
            selected = self._with_budget(selected, content)
            self._emit(selected)
            return selected

        if mode == "shadow":
            self._schedule_shadow(content, legacy, context)
            selected = replace(legacy, mode="shadow", **context_fields)
            selected = self._with_budget(selected, content)
            self._emit(selected)
            return selected

        if not self.jev_router.is_configured:
            selected = replace(
                legacy,
                mode="production",
                source="legacy",
                fallback_reason="not_configured",
                **context_fields,
            )
            selected = self._with_budget(selected, content)
            self._emit(selected)
            return selected

        decision = await self.jev_router.route(self._routing_input(content, context))
        if not decision.accepted or decision.route is None:
            selected = replace(
                legacy,
                mode="production",
                source="legacy",
                jev_route=decision.route,
                confidence=decision.confidence,
                latency_ms=decision.latency_ms,
                fallback_reason=self.fallback_reason(decision),
                **context_fields,
            )
            selected = self._with_budget(selected, content)
            self._emit(selected)
            return selected

        tier = self.tier_for_route(decision.route)
        selected = RouteSelection(
            model=tier.model,
            reasoning_effort=tier.reasoning_effort,
            route=decision.route,
            max_output_tokens=tier.max_output_tokens,
            mode="production",
            source="jev",
            legacy_route=legacy.route,
            jev_route=decision.route,
            confidence=decision.confidence,
            latency_ms=decision.latency_ms,
            **context_fields,
        )
        selected = self._with_budget(selected, content)
        self._emit(selected)
        return selected
