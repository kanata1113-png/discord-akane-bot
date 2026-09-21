import pytest

from services.adaptive_routing import AdaptiveRoutingController
from services.ai_control_plane import AIControlPlane
from services.jev_model_router import JevRouteDecision


class FakeProvider:
    mode = "production"
    is_configured = True
    confidence_threshold = 0.85
    timeout_seconds = 1.5

    async def route(self, content):
        return JevRouteDecision(
            route="reasoning",
            confidence=0.91,
            probabilities={"reasoning": 0.91},
            latency_ms=25,
            accepted=True,
            error=None,
        )


@pytest.mark.asyncio
async def test_control_plane_preserves_provider_acceptance_when_adaptive_disabled():
    captured = {}

    async def generate(**kwargs):
        captured.update(kwargs)
        return "ok"

    plane = AIControlPlane(provider=FakeProvider(), generate=generate)
    plane.provider.controller = AdaptiveRoutingController(enabled=False)

    reply, model, route = await plane.chat(
        user_name="tester",
        content="比較して",
        history=[],
    )

    assert reply == "ok"
    assert route == "reasoning"
    assert captured["model"] == model
    assert plane.provider.confidence_threshold == 0.85
    assert plane.provider.timeout_seconds == 1.5


def test_control_plane_snapshot_is_metadata_only():
    async def generate(**kwargs):
        return "ok"

    plane = AIControlPlane(provider=FakeProvider(), generate=generate)
    snapshot = plane.snapshot()
    values = snapshot.__dict__

    assert snapshot.version == "3.1"
    assert values["router_mode"] == "production"
    assert "content" not in values
    assert "history" not in values
    assert "user" not in values
