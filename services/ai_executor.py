from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI

from config import Config
from services.response_guard import ResponseGuard


logger = logging.getLogger("AkaneBot")


class AIExecutor:
    """OpenAI execution boundary used by the AI platform facade."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self.client = client

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        history=None,
        reasoning_effort: str = "low",
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
            response = await asyncio.wait_for(
                self.client.responses.create(
                    model=model,
                    input=input_messages,
                    reasoning={"effort": reasoning_effort},
                    max_output_tokens=max_tokens,
                ),
                timeout=90,
            )

            text = (response.output_text or "").strip()
            status = getattr(response, "status", None)
            incomplete_details = getattr(response, "incomplete_details", None)
            incomplete_reason = getattr(incomplete_details, "reason", None)

            check = ResponseGuard.check(text, incomplete=status == "incomplete")
            if not check.ok:
                logger.warning(
                    "AI response guard | reason=%s | model=%s | effort=%s | "
                    "status=%s | max_output_tokens=%s",
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
                if incomplete_reason == "max_output_tokens":
                    if text:
                        return f"{text}\n\n{Config.INCOMPLETE_OUTPUT_MSG}"
                    return Config.INCOMPLETE_OUTPUT_MSG

            return text

        except asyncio.TimeoutError:
            logger.warning(
                "OpenAI timeout | model=%s | effort=%s",
                model,
                reasoning_effort,
            )
            return Config.TIMEOUT_MSG

        except Exception as exc:
            logger.exception(
                "OpenAI API error | model=%s | effort=%s | error=%s",
                model,
                reasoning_effort,
                exc,
            )
            return Config.ERROR_MSG
