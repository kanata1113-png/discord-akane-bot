from __future__ import annotations

from dataclasses import dataclass

from services.adaptive_routing import AdaptiveRoutingController
from services.router_provider import RouterProvider


@dataclass(frozen=True)
class AdaptiveRouteDecision:
    route: str | None
    confidence: float
    probabilities: dict[str, float]
    latency_ms: int
    accepted: bool
    error: str | None = None
    policy_threshold: float | None = None
    policy_profile: str | None = None


class AdaptiveRouterProvider:
    """Feature-gated provider decorator for route-specific acceptance policy."""

    def __init__(
        self,
        provider: RouterProvider,
        controller: AdaptiveRoutingController | None = None,
    ) -> None:
        self.provider = provider
        self.controller = controller or AdaptiveRoutingController()
        self.mode = provider.mode

    @property
    def is_configured(self) -> bool:
        return self.provider.is_configured

    @property
    def confidence_threshold(self) -> float:
        return float(getattr(self.provider, "confidence_threshold", 0.85))

    @property
    def timeout_seconds(self) -> float:
        return float(getattr(self.provider, "timeout_seconds", 1.5))

    @property
    def adaptive_policy_enabled(self) -> bool:
        return self.controller.enabled

    async def route(self, content: str) -> AdaptiveRouteDecision:
        decision = await self.provider.route(content)
        acceptance = self.controller.evaluate(decision)
        return AdaptiveRouteDecision(
            route=decision.route,
            confidence=decision.confidence,
            probabilities=dict(decision.probabilities),
            latency_ms=decision.latency_ms,
            accepted=acceptance.accepted,
            error=decision.error,
            policy_threshold=acceptance.threshold,
            policy_profile=acceptance.profile_name,
        )
