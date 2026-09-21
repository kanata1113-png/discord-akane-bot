from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseCheck:
    ok: bool
    reason: str | None = None


class ResponseGuard:
    """Deterministic, no-LLM response checks.

    This layer intentionally does not judge factual quality. It only detects
    mechanical output problems that are safe to identify without another model.
    """

    @staticmethod
    def check(text: str, *, incomplete: bool = False) -> ResponseCheck:
        body = (text or "").strip()
        if incomplete:
            return ResponseCheck(False, "incomplete")
        if not body:
            return ResponseCheck(False, "empty")
        if len(body) < 2:
            return ResponseCheck(False, "too_short")
        return ResponseCheck(True, None)
