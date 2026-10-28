from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from uuid import uuid4

from openai import AsyncOpenAI

from config import Config
from services.cost_telemetry import CostTelemetry, UsageEvent
from services.response_guard import ResponseGuard
from services.token_efficiency import (
    RetryPolicy,
    RuntimeInputFootprint,
    measure_input_footprint,
)


logger = logging.getLogger("AkaneBot")


class AIExecutor:
    """OpenAI execution boundary used by the AI platform facade."""

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        cost_telemetry: CostTelemetry | None = None,
    ) -> None:
        self.client = client
        self.cost_telemetry = cost_telemetry or CostTelemetry()

    @staticmethod
    def _usage_value(usage, name: str) -> int:
        value = getattr(usage, name, 0) if usage is not None else 0
        return int(value or 0)

    def _record_usage(
        self,
        response,
        *,
        model: str,
        route: str,
        reasoning_effort: str,
        latency_ms: int,
        completed: bool,
        logical_request_id: str,
        feature: str,
        call_kind: str,
        attempt: int,
        footprint: RuntimeInputFootprint,
        incomplete_reason: str | None = None,
    ) -> None:
        usage = getattr(response, "usage", None)
        input_tokens = self._usage_value(usage, "input_tokens")
        output_tokens = self._usage_value(usage, "output_tokens")
        total_tokens = (
            self._usage_value(usage, "total_tokens")
            or input_tokens + output_tokens
        )
        input_details = getattr(usage, "input_tokens_details", None)
        output_details = getattr(usage, "output_tokens_details", None)
        cached = self._usage_value(input_details, "cached_tokens")
        reasoning = self._usage_value(output_details, "reasoning_tokens")
        self.cost_telemetry.record(
            UsageEvent(
                model=model,
                route=route,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cached_tokens=cached,
                reasoning_tokens=reasoning,
                reasoning_effort=reasoning_effort,
                latency_ms=latency_ms,
                estimated_cost_units=CostTelemetry.estimate_actual_units(
                    model,
                    input_tokens,
                    output_tokens,
                    route=route,
                    reasoning_effort=reasoning_effort,
                ),
                completed=completed,
                logical_request_id=logical_request_id,
                feature=feature,
                call_kind=call_kind,
                attempt=attempt,
                system_prompt_chars=footprint.system_chars,
                history_chars=footprint.history_chars,
                user_chars=footprint.user_chars,
                estimated_input_tokens=footprint.total_estimated_tokens,
                incomplete_reason=incomplete_reason,
            )
        )

    def _record_failure(
        self,
        *,
        model: str,
        route: str,
        reasoning_effort: str,
        latency_ms: int,
        logical_request_id: str,
        feature: str,
        call_kind: str,
        attempt: int,
        footprint: RuntimeInputFootprint,
        error_type: str,
        status_code: int | None = None,
    ) -> None:
        self.cost_telemetry.record(
            UsageEvent(
                model=model,
                route=route,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                reasoning_effort=reasoning_effort,
                latency_ms=latency_ms,
                estimated_cost_units=0.0,
                completed=False,
                logical_request_id=logical_request_id,
                feature=feature,
                call_kind=call_kind,
                attempt=attempt,
                system_prompt_chars=footprint.system_chars,
                history_chars=footprint.history_chars,
                user_chars=footprint.user_chars,
                estimated_input_tokens=footprint.total_estimated_tokens,
                error_type=error_type,
                status_code=status_code,
            )
        )

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
        feature: str = "unknown",
        logical_request_id: str | None = None,
    ) -> str:
        input_messages = [{"role": "system", "content": system}]
        usable_history: list[dict[str, str]] = []
        if history:
            for item in history:
                role = item.get("role")
                content = item.get("content", "")
                if role not in {"user", "assistant"} or not content:
                    continue
                message = {"role": role, "content": content}
                usable_history.append(message)
                input_messages.append(message)
        input_messages.append({"role": "user", "content": user})

        request_id = logical_request_id or uuid4().hex
        footprint = measure_input_footprint(
            system=system,
            user=user,
            history=usable_history,
        )

        max_attempts = RetryPolicy.MAX_TRANSIENT_RETRIES + 1
        for attempt in range(1, max_attempts + 1):
            call_kind = "primary" if attempt == 1 else "retry"
            started = perf_counter()
            try:
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
                status = getattr(response, "status", None)
                incomplete_details = getattr(
                    response,
                    "incomplete_details",
                    None,
                )
                incomplete_reason = getattr(
                    incomplete_details,
                    "reason",
                    None,
                )
                self._record_usage(
                    response,
                    model=model,
                    route=route,
                    reasoning_effort=reasoning_effort,
                    latency_ms=latency_ms,
                    completed=status != "incomplete",
                    logical_request_id=request_id,
                    feature=feature,
                    call_kind=call_kind,
                    attempt=attempt,
                    footprint=footprint,
                    incomplete_reason=incomplete_reason,
                )

                text = (response.output_text or "").strip()
                check = ResponseGuard.check(
                    text,
                    incomplete=status == "incomplete",
                )
                if not check.ok:
                    logger.warning(
                        "AI response guard | reason=%s | model=%s | "
                        "effort=%s | status=%s | max_output_tokens=%s",
                        check.reason,
                        model,
                        reasoning_effort,
                        status,
                        max_tokens,
                    )
                if status == "incomplete":
                    logger.warning(
                        "AI response incomplete | model=%s | effort=%s | "
                        "reason=%s | max_output_tokens=%s",
                        model,
                        reasoning_effort,
                        incomplete_reason,
                        max_tokens,
                    )
                    # Explicit efficiency invariant: never repeat the same prompt
                    # on the same model after MAX_TOKENS exhaustion.
                    if incomplete_reason == "max_output_tokens":
                        if text:
                            return f"{text}\n\n{Config.INCOMPLETE_OUTPUT_MSG}"
                        return Config.INCOMPLETE_OUTPUT_MSG
                return text

            except asyncio.TimeoutError:
                latency_ms = int((perf_counter() - started) * 1000)
                self._record_failure(
                    model=model,
                    route=route,
                    reasoning_effort=reasoning_effort,
                    latency_ms=latency_ms,
                    logical_request_id=request_id,
                    feature=feature,
                    call_kind=call_kind,
                    attempt=attempt,
                    footprint=footprint,
                    error_type="timeout",
                )
                logger.warning(
                    "OpenAI timeout | model=%s | effort=%s",
                    model,
                    reasoning_effort,
                )
                return Config.TIMEOUT_MSG

            except Exception as exc:
                latency_ms = int((perf_counter() - started) * 1000)
                status_code = getattr(exc, "status_code", None)
                error_type = (
                    f"http_{status_code}"
                    if status_code is not None
                    else exc.__class__.__name__
                )
                self._record_failure(
                    model=model,
                    route=route,
                    reasoning_effort=reasoning_effort,
                    latency_ms=latency_ms,
                    logical_request_id=request_id,
                    feature=feature,
                    call_kind=call_kind,
                    attempt=attempt,
                    footprint=footprint,
                    error_type=error_type,
                    status_code=status_code,
                )

                if RetryPolicy.should_retry(
                    status_code=status_code,
                    attempt=attempt,
                ):
                    logger.warning(
                        "OpenAI transient retry | model=%s | effort=%s | "
                        "status=%s | attempt=%s",
                        model,
                        reasoning_effort,
                        status_code,
                        attempt,
                    )
                    await asyncio.sleep(0.25)
                    continue

                logger.exception(
                    "OpenAI API error | model=%s | effort=%s | error=%s",
                    model,
                    reasoning_effort,
                    exc,
                )
                return Config.ERROR_MSG

        return Config.ERROR_MSG
