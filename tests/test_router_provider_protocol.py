import pytest
from dataclasses import dataclass

from services.routing_policy import RoutingPolicy


@dataclass(frozen=True)
class GenericDecision:
    route: str | None
    confidence: float
    probabilities: dict[str, float]
    latency_ms: int
    accepted: bool
    error: str | None = None


class GenericRouter:
    mode = "production"
    is_configured = True

    async def route(self, content: str) -> GenericDecision:
        return GenericDecision(
            route="normal-chat",
            confidence=0.99,
            probabilities={"normal-chat": 0.99},
            latency_ms=1,
            accepted=True,
        )


@pytest.mark.asyncio
async def test_routing_policy_accepts_structural_provider_without_jev_type():
    selection = await RoutingPolicy(GenericRouter()).select("こんにちは")
    assert selection.route == "normal-chat"
    assert selection.source == "jev"
