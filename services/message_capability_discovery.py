from __future__ import annotations

from dataclasses import dataclass

from services.capability_catalog import DISCOVERY_SPECS
from services.capability_discovery import DiscoveryCandidate, discover_locally
from services.jev_discovery_reranker import DiscoveryReranker


@dataclass(frozen=True, slots=True)
class MessageDiscoveryResult:
    should_show_panel: bool
    candidates: tuple[DiscoveryCandidate, ...]
    source: str
    confidence: float = 0.0


TICKET_TARGET_MARKERS = (
    "問い合わせ",
    "チケット",
    "ticket",
    "管理人",
    "管理者",
    "運営",
    "スタッフ",
    "staff",
)
TICKET_ACTION_MARKERS = (
    "問い合わせたい",
    "問い合わせしたい",
    "問い合わせをしたい",
    "相談したい",
    "連絡したい",
    "チケットを作",
    "チケット作",
    "ticketを作",
    "ticket作",
    "送信したい",
)


def discover_ticket_intent(content: str) -> DiscoveryCandidate | None:
    """Recognize explicit support/contact actions without routing explanation chat.

    Ticket is intentionally kept outside the 18-capability v4 general catalog so
    its addition does not mutate the frozen slash/capability surface. It is a
    native interaction entry routed before advisory Jev ranking.
    """

    text = (content or "").strip().lower()
    if not text or len(text) > 180:
        return None
    if not any(marker in text for marker in TICKET_TARGET_MARKERS):
        return None
    if not any(marker in text for marker in TICKET_ACTION_MARKERS):
        return None
    if any(marker in text for marker in ("とは", "意味", "教えて", "説明して")):
        return None
    return DiscoveryCandidate(
        capability_id="ticket_create",
        name="🎫 問い合わせを書く",
        description="管理人・運営への非公開問い合わせTicketを作成",
        slash_command=None,
        score=20.0,
        matched_terms=("ticket_intent",),
    )


async def discover_message_capabilities(
    content: str,
    *,
    reranker: DiscoveryReranker,
) -> MessageDiscoveryResult:
    ticket = discover_ticket_intent(content)
    if ticket is not None:
        return MessageDiscoveryResult(
            True,
            (ticket,),
            "local_ticket_intent",
            1.0,
        )

    local = discover_locally(content, DISCOVERY_SPECS)
    if not local.should_route:
        return MessageDiscoveryResult(False, (), local.reason)

    reranked = await reranker.rerank(content, local.candidates)
    return MessageDiscoveryResult(
        True,
        reranked.candidates,
        reranked.source,
        reranked.confidence,
    )
