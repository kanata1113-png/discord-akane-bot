from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx


logger = logging.getLogger("AkaneBot")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def jev_shadow_enabled() -> bool:
    """Shadow mode is on by default; without a key it performs no network call."""
    return _env_flag("JEV_ROUTER_SHADOW", True)


@dataclass(frozen=True)
class JevRouteDecision:
    route: str | None
    confidence: float
    probabilities: dict[str, float]
    latency_ms: int
    accepted: bool
    error: str | None = None


class JevModelRouter:
    """Small, fail-safe Jev client used only for model-routing decisions."""

    ROUTE_CRITERIA = {
        "normal-chat": (
            "Casual conversation, greetings, simple factual questions, "
            "straightforward explanations, and requests answerable without "
            "multi-step analysis."
        ),
        "reasoning": (
            "Requests needing comparison, causal analysis, interpretation of "
            "law or institutions, multiple interacting points, argument "
            "analysis, or other non-trivial reasoning."
        ),
        "deep-reasoning": (
            "Explicit requests for deep, rigorous, systematic, multi-angle, "
            "or highly constrained analysis where substantially more reasoning "
            "than an ordinary analytical answer is warranted."
        ),
    }

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
    def from_environment(cls) -> "JevModelRouter":
        return cls(
            api_key=os.getenv("TYPESAFE_API_KEY"),
            endpoint=os.getenv(
                "JEV_ROUTER_ENDPOINT",
                "https://api.typesafe.ai/v1/systemone",
            ),
            model=os.getenv("JEV_ROUTER_MODEL", "jev-latest"),
            confidence_threshold=float(
                os.getenv("JEV_ROUTER_CONFIDENCE", "0.85")
            ),
            timeout_seconds=float(
                os.getenv("JEV_ROUTER_TIMEOUT_SECONDS", "3.0")
            ),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def route(self, content: str) -> JevRouteDecision:
        if not self.is_configured:
            return JevRouteDecision(
                route=None,
                confidence=0.0,
                probabilities={},
                latency_ms=0,
                accepted=False,
                error="missing_api_key",
            )

        payload = {
            "model": self.model,
            "state": content,
            "questions": {
                "model_route": {
                    "type": "choice",
                    "instructions": (
                        "Choose the minimum model-routing tier that can answer "
                        "the user's message well. Prefer normal-chat when the "
                        "task is straightforward; use reasoning only when real "
                        "analysis is needed; reserve deep-reasoning for clearly "
                        "demanding analysis."
                    ),
                    "criteria": self.ROUTE_CRITERIA,
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
            return self._parse_response(data, latency_ms=latency_ms)

        except Exception as exc:
            latency_ms = int((perf_counter() - started) * 1000)
            logger.warning(
                "Jev route failed | error=%s | latency_ms=%s",
                exc,
                latency_ms,
            )
            return JevRouteDecision(
                route=None,
                confidence=0.0,
                probabilities={},
                latency_ms=latency_ms,
                accepted=False,
                error=type(exc).__name__,
            )

    def _parse_response(
        self,
        data: dict[str, Any],
        *,
        latency_ms: int,
    ) -> JevRouteDecision:
        answer = data.get("answers", {}).get("model_route", {})
        route = answer.get("choice")
        confidence = float(answer.get("confidence", 0.0) or 0.0)
        raw_probabilities = answer.get("probabilities", {}) or {}
        probabilities = {
            str(key): float(value)
            for key, value in raw_probabilities.items()
        }

        if route not in self.ROUTE_CRITERIA:
            return JevRouteDecision(
                route=None,
                confidence=confidence,
                probabilities=probabilities,
                latency_ms=latency_ms,
                accepted=False,
                error="invalid_route",
            )

        return JevRouteDecision(
            route=route,
            confidence=confidence,
            probabilities=probabilities,
            latency_ms=latency_ms,
            accepted=confidence >= self.confidence_threshold,
            error=None,
        )
