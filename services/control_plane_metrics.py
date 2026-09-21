from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any


logger = logging.getLogger("AkaneBot")


@dataclass(frozen=True)
class ControlPlaneEvent:
    event_id: str | None
    phase: str
    route: str | None = None
    source: str | None = None
    intent: str | None = None
    pipeline: str | None = None
    model: str | None = None
    max_output_tokens: int | None = None
    budget_reason: str | None = None
    guard_result: str | None = None
    latency_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if value is not None
        }


class ControlPlaneTelemetry:
    """Metadata-only event chain for orchestration stages.

    Message bodies, user IDs, guild IDs and channel IDs are intentionally not
    part of the event schema.
    """

    def emit(self, event: ControlPlaneEvent) -> None:
        logger.info(
            "CONTROL_PLANE_EVENT %s",
            json.dumps(
                event.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
