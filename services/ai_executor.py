from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from openai import AsyncOpenAI

from config import Config
from services.cost_telemetry import CostTelemetry, UsageEvent
from services.response_guard import ResponseGuard


logger = logging.getLogger("AkaneBot")


class AIExecutor:
    """OpenAI execution boundary used by the AI platform facade."""

    def __init__(self, client: AsyncOpenAI, *, cost_telemetry: CostTelemetry | None = None) -> None:
        self.client = client
        self.cost_telemetry = cost_telemetry or CostTelemetry()

    @staticmethod
    def _usage_value(usage, name: str) -> int:
        value = getattr(usage, name, 0) if usage is not None else 0
        return int(value or 0)

    def _record_usage(self, response, *, model: str, route: str, latency_ms: int) -> None:
        usage = getattr(response, "usage", None)
        input_tokens = self._usage_value(usage, "input_tokens")
        output_tokens = self._usage_value(usage, "output_tokens")
        total_tokens = self._usage_value(usage, "total_tokens") or input_tokens + output_tokens
        input_details = getattr(usage, "input_tokens_details", None)
        output_details = getattr(usage, "output_tokens_details", None)
        cached = self._usage_value(input_details, "cached_tokens")
        reasoning = self._usage_value(output_details, "reasoning_tokens")
        self.cost_telemetry.record(UsageEvent(
            model=model,
            route=route,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached,
            reasoning_tokens=reasoning,
            latency_ms=latency_ms,
            estimated_cost_units=CostTelemetry.estimate_actual_units(model, input_tokens, output_tokens),
        ))

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        history=None,
        reasoning_effort: str = "low",
        route: str = "unknown",
    ) -> str:
        input_messages = [{"role": "system", "content": system}]
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content", "")
                if role not in {"user", "assistant"} or not content:
                    continue
                input_messages.append({"role": role, "content": content})
        input_messages.append({"role": "user", "content": user})

        try:
            started = perf_counter()
            response = await asyncio.wait_for(
                self.client.responses.create(
                    model=model,
                    input=input_messages,
                    reasoning={"effort": reasoning_effort},
                    max_output_tokens=max_tokens,
                ),
                timeout=90,
            )
            latency_ms = int((perf_counter() - started) * 1000)
            self._record_usage(response, model=model, route=route, latency_ms=latency_ms)

            text = (response.output_text or "").strip()
            status = getattr(response, "status", None)
            incomplete_details = getattr(response, "incomplete_details", None)
            incomplete_reason = getattr(incomplete_details, "reason", None)
            check = ResponseGuard.check(text, incomplete=status == "incomplete")
            if not check.ok:
                logger.warning("AI response guard | reason=%s | model=%s | effort=%s | status=%s | max_output_tokens=%s", check.reason, model, reasoning_effort, status, max_tokens)
            if status == "incomplete":
                logger.warning("AI response incomplete | model=%s | effort=%s | reason=%s | max_output_tokens=%s", model, reasoning_effort, incomplete_reason, max_tokens)
                if incomplete_reason == "max_output_tokens":
                    if text:
                        return f"{text}\n\n{Config.INCOMPLETE_OUTPUT_MSG}"
                    return Config.INCOMPLETE_OUTPUT_MSG
            return text
        except asyncio.TimeoutError:
            logger.warning("OpenAI timeout | model=%s | effort=%s", model, reasoning_effort)
            return Config.TIMEOUT_MSG
        except Exception as exc:
            logger.exception("OpenAI API error | model=%s | effort=%s | error=%s", model, reasoning_effort, exc)
            return Config.ERROR_MSG
