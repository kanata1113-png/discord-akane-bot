from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping


class TokenEstimator:
    """Deterministic local token estimator used only for budgeting/telemetry.

    It intentionally over-estimates Japanese/non-ASCII text (roughly one token
    per character) and uses four ASCII characters per token. It never replaces
    provider usage accounting; actual API usage remains authoritative.
    """

    @staticmethod
    def estimate_text(text: str | None) -> int:
        if not text:
            return 0
        ascii_chars = sum(1 for char in text if ord(char) < 128)
        non_ascii_chars = len(text) - ascii_chars
        return non_ascii_chars + math.ceil(ascii_chars / 4)

    @classmethod
    def estimate_messages(
        cls,
        messages: Iterable[Mapping[str, object]] | None,
    ) -> int:
        total = 0
        for item in messages or []:
            content = item.get("content")
            if not isinstance(content, str) or not content:
                continue
            # Small per-message envelope for role/serialization overhead.
            total += cls.estimate_text(content) + 4
        return total

    @classmethod
    def truncate_to_tokens(cls, text: str, token_budget: int) -> str:
        budget = max(0, int(token_budget))
        if budget <= 0:
            return ""
        if cls.estimate_text(text) <= budget:
            return text

        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if cls.estimate_text(text[:mid]) <= max(0, budget - 1):
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + "…"


@dataclass(frozen=True)
class RuntimeInputFootprint:
    system_chars: int
    history_chars: int
    user_chars: int
    system_estimated_tokens: int
    history_estimated_tokens: int
    user_estimated_tokens: int

    @property
    def total_estimated_tokens(self) -> int:
        return (
            self.system_estimated_tokens
            + self.history_estimated_tokens
            + self.user_estimated_tokens
        )


def measure_input_footprint(
    *,
    system: str,
    user: str,
    history=None,
) -> RuntimeInputFootprint:
    history_chars = sum(
        len(item.get("content", ""))
        for item in history or []
        if isinstance(item, Mapping)
        and isinstance(item.get("content"), str)
    )
    return RuntimeInputFootprint(
        system_chars=len(system or ""),
        history_chars=history_chars,
        user_chars=len(user or ""),
        system_estimated_tokens=TokenEstimator.estimate_text(system),
        history_estimated_tokens=TokenEstimator.estimate_messages(history),
        user_estimated_tokens=TokenEstimator.estimate_text(user),
    )


class RetryPolicy:
    """Explicit retry envelope for model calls.

    The OpenAI SDK retry layer is disabled by AiManager so model-call
    amplification is visible here. Only one same-model retry is allowed for
    transient HTTP failures. Incomplete MAX_TOKENS generations are never
    retried on the same model.
    """

    RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
    MAX_TRANSIENT_RETRIES = 1

    @classmethod
    def should_retry(
        cls,
        *,
        status_code: int | None,
        attempt: int,
        incomplete_reason: str | None = None,
    ) -> bool:
        if incomplete_reason == "max_output_tokens":
            return False
        if attempt > cls.MAX_TRANSIENT_RETRIES:
            return False
        return status_code in cls.RETRYABLE_STATUS_CODES
