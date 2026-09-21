import pytest

from services.evaluation import (
    RoutingBenchmarkCase,
    TelemetryReplayEvent,
    evaluate_routing_cases,
    summarize_telemetry,
)
from services.jev_model_router import JevRouteDecision
from services.routing_policy import RoutingPolicy


@pytest.mark.asyncio
async def test_benchmark_uses_explicit_fixture_content_not_telemetry():
    class FakeRouter:
        mode = "production"
        is_configured = True

        async def route(self, content):
            return JevRouteDecision(
                route="reasoning",
                confidence=0.99,
                probabilities={"reasoning": 0.99},
                latency_ms=10,
                accepted=True,
                error=None,
            )

    cases = [
        RoutingBenchmarkCase(
            case_id="analysis-1",
            content="AとBを比較して",
            expected_route="reasoning",
        )
    ]
    results = await evaluate_routing_cases(RoutingPolicy(FakeRouter()), cases)
    assert results[0].matched is True
    assert results[0].selected_route == "reasoning"


def test_telemetry_replay_is_metadata_only_and_summarizable():
    event = TelemetryReplayEvent.from_mapping(
        {
            "event_id": "abc",
            "selected_route": "reasoning",
            "legacy_route": "normal-chat",
            "jev_route": "reasoning",
            "confidence": 0.91,
            "fallback_reason": None,
            "followup_like": True,
            "previous_route": "reasoning",
            "intent_hint": "analysis",
            "model": "test-model",
            "latency_ms": 700,
            "content": "must not be represented",
        }
    )
    assert not hasattr(event, "content")
    summary = summarize_telemetry([event])
    assert summary["events"] == 1
    assert summary["followups"] == 1
    assert summary["mean_confidence"] == 0.91
