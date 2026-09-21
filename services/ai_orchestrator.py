from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from config import Config
from services.prompt_builder import PromptBuilder
from services.routing_policy import RoutingPolicy


logger = logging.getLogger("AkaneBot")

GenerateCallable = Callable[..., Awaitable[str]]


class AIOrchestrator:
    """Coordinates chat routing, prompt construction and model execution.

    It owns no Discord state and no database state. AiManager remains the
    compatibility facade for existing call sites.
    """

    def __init__(
        self,
        routing_policy: RoutingPolicy,
        generate: GenerateCallable,
    ) -> None:
        self.routing_policy = routing_policy
        self.generate = generate

    async def chat(
        self,
        *,
        user_name: str,
        content: str,
        history=None,
    ) -> tuple[str, str, str]:
        selection = await self.routing_policy.select(content, history=history)

        regulation_mode = any(
            keyword in content for keyword in Config.REGULATION_KEYWORDS
        )
        system_prompt = PromptBuilder.chat_system_prompt(
            regulation_mode=regulation_mode
        )
        user_prompt = PromptBuilder.chat_user_prompt(user_name, content)

        logger.info(
            "AI route selected | route=%s | source=%s | model=%s | "
            "effort=%s | max_output_tokens=%s | history=%s | event_id=%s",
            selection.route,
            selection.source,
            selection.model,
            selection.reasoning_effort,
            selection.max_output_tokens,
            len(history) if history else 0,
            selection.event_id,
        )

        reply = await self.generate(
            system=system_prompt,
            user=user_prompt,
            model=selection.model,
            max_tokens=selection.max_output_tokens,
            history=history,
            reasoning_effort=selection.reasoning_effort,
        )

        return reply, selection.model, selection.route
