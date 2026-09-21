from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from services.adaptive_router_provider import AdaptiveRouterProvider
from services.ai_orchestrator import AIOrchestrator
from services.jev_model_router import JevModelRouter
from services.routing_metrics import RoutingTelemetry
from services.routing_policy import RoutingPolicy


GenerateCallable = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class ControlPlaneSnapshot:
    version: str
    router_mode: str
    router_configured: bool
    adaptive_routing_enabled: bool
    context_hints_enabled: bool
    adaptive_budget_v1_enabled: bool
    intent_controller_enabled: bool
    budget_controller_v2_enabled: bool


class AIControlPlane:
    """Composition root for Akane's AI request control plane.

    The control plane wires provider selection, routing policy, orchestration,
    budget/intent controllers and telemetry without owning Discord or database
    state. Behavior-changing controllers remain governed by their feature flags.
    """

    VERSION = "3.0"

    def __init__(
        self,
        *,
        provider,
        generate: GenerateCallable,
        routing_telemetry: RoutingTelemetry | None = None,
    ) -> None:
        self.base_provider = provider
        self.provider = AdaptiveRouterProvider(provider)
        self.routing_telemetry = routing_telemetry or RoutingTelemetry()
        self.routing_policy = RoutingPolicy(
            self.provider,
            telemetry=self.routing_telemetry,
        )
        self.orchestrator = AIOrchestrator(
            self.routing_policy,
            generate,
        )

    @classmethod
    def from_environment(
        cls,
        *,
        generate: GenerateCallable,
        routing_telemetry: RoutingTelemetry | None = None,
    ) -> "AIControlPlane":
        return cls(
            provider=JevModelRouter.from_environment(),
            generate=generate,
            routing_telemetry=routing_telemetry,
        )

    async def chat(self, *, user_name: str, content: str, history=None):
        return await self.orchestrator.chat(
            user_name=user_name,
            content=content,
            history=history,
        )

    def snapshot(self) -> ControlPlaneSnapshot:
        adaptive = self.provider.controller
        return ControlPlaneSnapshot(
            version=self.VERSION,
            router_mode=self.provider.mode,
            router_configured=self.provider.is_configured,
            adaptive_routing_enabled=adaptive.enabled,
            context_hints_enabled=self.routing_policy.context_hints_enabled,
            adaptive_budget_v1_enabled=self.routing_policy.adaptive_budget_enabled,
            intent_controller_enabled=self.orchestrator.intent_controller.enabled,
            budget_controller_v2_enabled=self.orchestrator.budget_controller.enabled,
        )
