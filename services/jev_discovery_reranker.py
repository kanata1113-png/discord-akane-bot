from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, Sequence

import httpx

from services.capability_discovery import DiscoveryCandidate


logger = logging.getLogger("AkaneBot")


@dataclass(frozen=True, slots=True)
class DiscoveryRerankResult:
    candidates: tuple[DiscoveryCandidate, ...]
    accepted: bool
    confidence: float
    latency_ms: int
    source: str
    error: str | None = None


class DiscoveryReranker(Protocol):
    async def rerank(
        self,
        content: str,
        candidates: Sequence[DiscoveryCandidate],
    ) -> DiscoveryRerankResult:
        ...


class JevDiscoveryReranker:
    """Advisory-only Jev reranker for an already-small local shortlist."""

    def __init__(
        self,
        *,
        api_key: str | None,
        endpoint: str,
        model: str,
        confidence_threshold: float,
        timeout_seconds: float,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.endpoint = endpoint
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "JevDiscoveryReranker":
        return cls(
            api_key=os.getenv("TYPESAFE_API_KEY"),
            endpoint=os.getenv(
                "JEV_ROUTER_ENDPOINT",
                "https://api.typesafe.ai/v1/systemone",
            ),
            model=os.getenv("JEV_ROUTER_MODEL", "jev-latest"),
            confidence_threshold=float(
                os.getenv("JEV_DISCOVERY_CONFIDENCE", "0.75")
            ),
            timeout_seconds=float(
                os.getenv("JEV_DISCOVERY_TIMEOUT_SECONDS", "1.0")
            ),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def rerank(
        self,
        content: str,
        candidates: Sequence[DiscoveryCandidate],
    ) -> DiscoveryRerankResult:
        local = tuple(candidates)
        if len(local) <= 1:
            return DiscoveryRerankResult(
                local, True, 1.0, 0, "local_unambiguous"
            )
        if not self.is_configured:
            return self._fallback(local, error="missing_api_key")

        criteria = {
            item.capability_id: (
                f"{item.name}: {item.description}. "
                f"Slash command: {item.slash_command or 'none'}."
            )
            for item in local
        }
        payload = {
            "model": self.model,
            "state": content,
            "questions": {
                "capability": {
                    "type": "choice",
                    "instructions": (
                        "Choose the single candidate capability that most "
                        "closely matches the user's requested action. Choose "
                        "only from the supplied candidates. This is ranking "
                        "only; do not infer permission or execute anything."
                    ),
                    "criteria": criteria,
                }
            },
        }

        started = perf_counter()
        try:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            latency_ms = int((perf_counter() - started) * 1000)
            return self._parse(data, local, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            logger.warning(
                "Jev discovery rerank failed | error=%s | latency_ms=%s",
                type(exc).__name__,
                latency_ms,
            )
            return self._fallback(
                local,
                error=type(exc).__name__,
                latency_ms=latency_ms,
            )

    def _parse(
        self,
        data: dict[str, Any],
        local: tuple[DiscoveryCandidate, ...],
        *,
        latency_ms: int,
    ) -> DiscoveryRerankResult:
        answer = data.get("answers", {}).get("capability", {})
        choice = answer.get("choice")
        confidence = float(answer.get("confidence", 0.0) or 0.0)
        by_id = {item.capability_id: item for item in local}

        if choice not in by_id:
            return self._fallback(
                local,
                error="invalid_choice",
                confidence=confidence,
                latency_ms=latency_ms,
            )
        if confidence < self.confidence_threshold:
            return self._fallback(
                local,
                error="low_confidence",
                confidence=confidence,
                latency_ms=latency_ms,
            )

        selected = by_id[choice]
        ordered = (selected,) + tuple(
            item for item in local if item.capability_id != choice
        )
        return DiscoveryRerankResult(
            ordered,
            True,
            confidence,
            latency_ms,
            "jev",
        )

    @staticmethod
    def _fallback(
        local: tuple[DiscoveryCandidate, ...],
        *,
        error: str,
        confidence: float = 0.0,
        latency_ms: int = 0,
    ) -> DiscoveryRerankResult:
        return DiscoveryRerankResult(
            local,
            False,
            confidence,
            latency_ms,
            "local_fallback",
            error,
        )
