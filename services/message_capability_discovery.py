from __future__ import annotations

from dataclasses import dataclass

from services.capability_discovery import (
    DiscoveryCandidate,
    discover_locally,
)
from services.jev_discovery_reranker import DiscoveryReranker
from services.progression_capabilities import (
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
    LEADERBOARD_SPEC,
    LEVEL_SPEC,
    PROFILE_SPEC,
    RANKINGS_SPEC,
    WEEKLY_SPEC,
)


DISCOVERY_SPECS = (
    LEVEL_SPEC,
    LEADERBOARD_SPEC,
    WEEKLY_SPEC,
    RANKINGS_SPEC,
    PROFILE_SPEC,
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
)


@dataclass(frozen=True, slots=True)
class MessageDiscoveryResult:
    should_show_panel: bool
    candidates: tuple[DiscoveryCandidate, ...]
    source: str
    confidence: float = 0.0


async def discover_message_capabilities(
    content: str,
    *,
    reranker: DiscoveryReranker,
) -> MessageDiscoveryResult:
    local = discover_locally(content, DISCOVERY_SPECS)
    if not local.should_route:
        return MessageDiscoveryResult(
            False,
            (),
            local.reason,
        )

    reranked = await reranker.rerank(content, local.candidates)
    return MessageDiscoveryResult(
        True,
        reranked.candidates,
        reranked.source,
        reranked.confidence,
    )
