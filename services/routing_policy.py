from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from config import Config
from services.jev_model_router import JevModelRouter, JevRouteDecision
from services.routing_metrics import RoutingMetric, RoutingTelemetry


logger = logging.getLogger("AkaneBot")


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


class RoutingPolicy:
    """Single model-routing policy for chat traffic.

    Jev is allowed to choose only the model tier. Domain-specific prompt
    augmentation (for example regulation/free-speech handling) stays outside
    this class so routing cannot silently change prompt behavior.
    """

    def __init__(
        self,
        jev_router: JevModelRouter,
        telemetry: RoutingTelemetry | None = None,
    ) -> None:
        self.jev_router = jev_router
        self.telemetry = telemetry or RoutingTelemetry()
        self._shadow_tasks: set[asyncio.Task] = set()

    @staticmethod
    def tier_for_route(route: str) -> ModelTier:
        if route == "deep-reasoning":
            return ModelTier(
                model=Config.REASONING_MODEL,
                reasoning_effort=Config.DEEP_REASONING_EFFORT,
                max_output_tokens=Config.DEEP_REASONING_MAX_TOKENS,
            )
        if route in {"reasoning", "regulation", "long-question"}:
            return ModelTier(
                model=Config.REASONING_MODEL,
                reasoning_effort=Config.REASONING_EFFORT,
                max_output_tokens=Config.REASONING_MAX_TOKENS,
            )
        return ModelTier(
            model=Config.CHAT_MODEL,
            reasoning_effort=Config.CHAT_REASONING_EFFORT,
            max_output_tokens=Config.NORMAL_CHAT_MAX_TOKENS,
        )

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

    def _emit(self, selection: RouteSelection) -> None:
        self.telemetry.emit(
            RoutingMetric(
                mode=selection.mode,
                source=selection.source,
                legacy_route=self.normalize_legacy_route(
                    selection.legacy_route
                ),
                selected_route=selection.route,
                jev_route=selection.jev_route,
                confidence=selection.confidence,
                latency_ms=selection.latency_ms,
                fallback_reason=selection.fallback_reason,
                model=selection.model,
                reasoning_effort=selection.reasoning_effort,
                max_output_tokens=selection.max_output_tokens,
            )
        )

    async def _observe_shadow(
        self,
        content: str,
        legacy: RouteSelection,
    ) -> None:
        if not self.jev_router.is_configured:
            return

        decision = await self.jev_router.route(content)
        legacy_normalized = self.normalize_legacy_route(legacy.route)

        self.telemetry.emit(
            RoutingMetric(
                event="shadow_observation",
                mode="shadow",
                source="legacy",
                legacy_route=legacy_normalized,
                selected_route=legacy.route,
                jev_route=decision.route,
                confidence=decision.confidence,
                latency_ms=decision.latency_ms,
                fallback_reason=(
                    None
                    if decision.accepted
                    else self.fallback_reason(decision)
                ),
                model=legacy.model,
                reasoning_effort=legacy.reasoning_effort,
                max_output_tokens=legacy.max_output_tokens,
            )
        )

    def _schedule_shadow(
        self,
        content: str,
        legacy: RouteSelection,
    ) -> None:
        if not self.jev_router.is_configured:
            return

        task = asyncio.create_task(self._observe_shadow(content, legacy))
        self._shadow_tasks.add(task)
        task.add_done_callback(self._shadow_tasks.discard)

    async def select(self, content: str) -> RouteSelection:
        legacy = self.legacy_selection(content)
        mode = getattr(self.jev_router, "mode", "legacy")

        if mode == "legacy":
            selected = RouteSelection(
                **{
                    **legacy.__dict__,
                    "mode": "legacy",
                }
            )
            self._emit(selected)
            return selected

        if mode == "shadow":
            self._schedule_shadow(content, legacy)
            selected = RouteSelection(
                **{
                    **legacy.__dict__,
                    "mode": "shadow",
                }
            )
            self._emit(selected)
            return selected

        if not self.jev_router.is_configured:
            selected = RouteSelection(
                model=legacy.model,
                reasoning_effort=legacy.reasoning_effort,
                route=legacy.route,
                max_output_tokens=legacy.max_output_tokens,
                mode="production",
                source="legacy",
                legacy_route=legacy.route,
                fallback_reason="not_configured",
            )
            self._emit(selected)
            return selected

        decision = await self.jev_router.route(content)

        if not decision.accepted or decision.route is None:
            selected = RouteSelection(
                model=legacy.model,
                reasoning_effort=legacy.reasoning_effort,
                route=legacy.route,
                max_output_tokens=legacy.max_output_tokens,
                mode="production",
                source="legacy",
                legacy_route=legacy.route,
                jev_route=decision.route,
                confidence=decision.confidence,
                latency_ms=decision.latency_ms,
                fallback_reason=self.fallback_reason(decision),
            )
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
        )
        self._emit(selected)
        return selected
