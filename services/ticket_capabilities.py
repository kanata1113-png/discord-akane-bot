from __future__ import annotations

from services.capability_core import CapabilityRisk, CapabilitySpec


TICKET_CREATE_CAPABILITY_ID = "ticket_create"

TICKET_CREATE_SPEC = CapabilitySpec(
    capability_id=TICKET_CREATE_CAPABILITY_ID,
    name="問い合わせTicket作成",
    description="管理人・運営への問い合わせ用の非公開Ticketを作成する",
    risk=CapabilityRisk.WRITE_CONFIRM,
    category="community",
    slash_command=None,
    requires_confirmation=True,
    discoverable=True,
    tags=(
        "ticket",
        "チケット",
        "問い合わせ",
        "管理人",
        "管理者",
        "運営",
        "サポート",
        "相談",
    ),
)
