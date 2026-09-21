import pytest

from services.capability_discovery import DiscoveryCandidate
from services.jev_discovery_reranker import JevDiscoveryReranker


def candidate(capability_id, score):
    return DiscoveryCandidate(
        capability_id=capability_id,
        name=capability_id,
        description=f"{capability_id} description",
        slash_command=f"/{capability_id}",
        score=score,
        matched_terms=(capability_id,),
    )


LOCAL = (
    candidate("weekly", 8.0),
    candidate("rankings", 4.0),
)


def reranker(*, api_key="test-key", threshold=0.75):
    return JevDiscoveryReranker(
        api_key=api_key,
        endpoint="https://example.invalid",
        model="jev-latest",
        confidence_threshold=threshold,
        timeout_seconds=0.1,
    )


@pytest.mark.asyncio
async def test_unambiguous_candidate_skips_jev_network():
    one = (candidate("level", 5.0),)
    result = await reranker(api_key=None).rerank("レベルを見たい", one)

    assert result.candidates == one
    assert result.accepted is True
    assert result.source == "local_unambiguous"


@pytest.mark.asyncio
async def test_missing_api_key_falls_back_to_local_order():
    result = await reranker(api_key=None).rerank(
        "今週のランキングを見たい",
        LOCAL,
    )

    assert result.candidates == LOCAL
    assert result.accepted is False
    assert result.source == "local_fallback"
    assert result.error == "missing_api_key"


def test_valid_high_confidence_choice_moves_only_selected_candidate_first():
    service = reranker()
    result = service._parse(
        {
            "answers": {
                "capability": {
                    "choice": "rankings",
                    "confidence": 0.91,
                }
            }
        },
        LOCAL,
        latency_ms=12,
    )

    assert [item.capability_id for item in result.candidates] == [
        "rankings",
        "weekly",
    ]
    assert result.accepted is True
    assert result.source == "jev"
    assert result.confidence == 0.91


def test_low_confidence_preserves_local_order():
    service = reranker(threshold=0.75)
    result = service._parse(
        {
            "answers": {
                "capability": {
                    "choice": "rankings",
                    "confidence": 0.51,
                }
            }
        },
        LOCAL,
        latency_ms=8,
    )

    assert result.candidates == LOCAL
    assert result.accepted is False
    assert result.error == "low_confidence"


def test_invalid_choice_cannot_inject_capability():
    service = reranker()
    result = service._parse(
        {
            "answers": {
                "capability": {
                    "choice": "ban",
                    "confidence": 0.99,
                }
            }
        },
        LOCAL,
        latency_ms=7,
    )

    assert result.candidates == LOCAL
    assert result.accepted is False
    assert result.error == "invalid_choice"
    assert all(item.capability_id != "ban" for item in result.candidates)


@pytest.mark.asyncio
async def test_network_error_falls_back_without_execution(monkeypatch):
    class BrokenClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            raise TimeoutError("timeout")

    monkeypatch.setattr(
        "services.jev_discovery_reranker.httpx.AsyncClient",
        lambda **kwargs: BrokenClient(),
    )

    result = await reranker().rerank("今週のランキング", LOCAL)

    assert result.candidates == LOCAL
    assert result.accepted is False
    assert result.source == "local_fallback"
    assert result.error == "TimeoutError"
