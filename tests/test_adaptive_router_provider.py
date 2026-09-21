from dataclasses import dataclass

import pytest

from services.adaptive_router_provider import AdaptiveRouterProvider
from services.adaptive_routing import AdaptiveRoutingController


@dataclass(frozen=True)
class Decision:
    route: str | None
    confidence: float
    probabilities: dict[str, float]
    latency_ms: int
    accepted: bool
    error: str | None = None


class Provider:
    mode = "production"
    is_configured = True

    async def route(self, content: str) -> Decision:
        return Decision("reasoning", 0.83, {"reasoning": 0.83}, 10, False)


@pytest.mark.asyncio
async def test_disabled_decorator_preserves_provider_acceptance():
    wrapped = AdaptiveRouterProvider(
        Provider(), AdaptiveRoutingController(enabled=False)
    )
    result = await wrapped.route("compare")
    assert result.accepted is False


@pytest.mark.asyncio
async def test_enabled_decorator_uses_route_specific_threshold():
    wrapped = AdaptiveRouterProvider(
        Provider(), AdaptiveRoutingController(enabled=True)
    )
    result = await wrapped.route("compare")
    assert result.accepted is True
    assert result.policy_threshold == 0.82
