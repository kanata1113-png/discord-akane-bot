from __future__ import annotations

from typing import Mapping, Protocol


class RouteDecision(Protocol):
    route: str | None
    confidence: float
    probabilities: Mapping[str, float]
    latency_ms: int
    accepted: bool
    error: str | None


class RouterProvider(Protocol):
    """Structural interface for model-tier routing providers.

    Providers may be Jev-backed, rule-based, or experimental. RoutingPolicy
    depends only on this protocol and no longer needs a Jev-specific type.
    """

    mode: str

    @property
    def is_configured(self) -> bool: ...

    async def route(self, content: str) -> RouteDecision: ...
