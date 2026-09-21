import logging

from openai import AsyncOpenAI

from config import Config
from services.ai_executor import AIExecutor
from services.jev_model_router import JevModelRouter
from services.prompt_builder import PromptBuilder
from services.routing_metrics import RoutingTelemetry
from services.routing_policy import RoutingPolicy


logger = logging.getLogger("AkaneBot")


class AiManager:
    """Compatibility facade for Akane's v1 AI platform.

    Discord-facing call sites keep the historical AiManager API while routing,
    prompt construction and model execution are delegated to focused services.
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.executor = AIExecutor(self.client)
        self.jev_router = JevModelRouter.from_environment()
        self.routing_telemetry = RoutingTelemetry()
        self.routing_policy = RoutingPolicy(
            self.jev_router,
            telemetry=self.routing_telemetry,
        )

        logger.info(
            "AI platform initialized | version=1.0-candidate | "
            "jev_mode=%s | jev_configured=%s | "
            "confidence_threshold=%.2f | timeout_seconds=%.2f",
            self.jev_router.mode,
            self.jev_router.is_configured,
            self.jev_router.confidence_threshold,
            self.jev_router.timeout_seconds,
        )

    def _policy(self) -> RoutingPolicy:
        policy = getattr(self, "routing_policy", None)
        router = getattr(self, "jev_router", None)
        if router is None:
            router = JevModelRouter.from_environment()
            self.jev_router = router
        if policy is None or policy.jev_router is not router:
            telemetry = getattr(self, "routing_telemetry", None)
            policy = RoutingPolicy(router, telemetry=telemetry)
            self.routing_policy = policy
        return policy

    # ==========================================================================
    # Prompt compatibility
    # ==========================================================================

    @staticmethod
    def get_system_prompt(regulation_mode: bool = False) -> str:
        return PromptBuilder.chat_system_prompt(
            regulation_mode=regulation_mode
        )

    # ==========================================================================
    # Routing compatibility
    # ==========================================================================

    def select_chat_model(self, content: str) -> tuple[str, str, str]:
        selection = RoutingPolicy.legacy_selection(content)
        return (
            selection.model,
            selection.reasoning_effort,
            selection.route,
        )

    @staticmethod
    def _normalize_legacy_route_for_jev(route: str) -> str:
        return RoutingPolicy.normalize_legacy_route(route)

    @staticmethod
    def _route_config(route: str) -> tuple[str, str]:
        tier = RoutingPolicy.tier_for_route(route)
        return tier.model, tier.reasoning_effort

    @staticmethod
    def _jev_fallback_reason(decision) -> str:
        return RoutingPolicy.fallback_reason(decision)

    async def _run_jev_shadow(
        self,
        content: str,
        legacy_route: str,
    ) -> None:
        legacy = RoutingPolicy.legacy_selection(content)
        if legacy.route != legacy_route:
            tier = RoutingPolicy.tier_for_route(legacy_route)
            legacy = legacy.__class__(
                model=tier.model,
                reasoning_effort=tier.reasoning_effort,
                route=legacy_route,
                max_output_tokens=tier.max_output_tokens,
                mode="legacy",
                source="legacy",
                legacy_route=legacy_route,
            )
        await self._policy()._observe_shadow(content, legacy)

    def _schedule_jev_shadow(
        self,
        content: str,
        legacy_route: str,
    ) -> None:
        legacy = RoutingPolicy.legacy_selection(content)
        if legacy.route != legacy_route:
            tier = RoutingPolicy.tier_for_route(legacy_route)
            legacy = legacy.__class__(
                model=tier.model,
                reasoning_effort=tier.reasoning_effort,
                route=legacy_route,
                max_output_tokens=tier.max_output_tokens,
                mode="legacy",
                source="legacy",
                legacy_route=legacy_route,
            )
        self._policy()._schedule_shadow(content, legacy)

    async def _select_production_route(
        self,
        content: str,
        legacy_model: str,
        legacy_effort: str,
        legacy_route: str,
    ) -> tuple[str, str, str]:
        # The supplied legacy values are retained in the signature for
        # compatibility. RoutingPolicy independently recomputes the same
        # deterministic legacy baseline from content.
        selection = await self._policy().select(content)
        return (
            selection.model,
            selection.reasoning_effort,
            selection.route,
        )

    @staticmethod
    def select_chat_max_tokens(route: str) -> int:
        return RoutingPolicy.tier_for_route(route).max_output_tokens

    # ==========================================================================
    # OpenAI execution compatibility
    # ==========================================================================

    async def call_gpt(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        history=None,
        reasoning_effort: str = "low",
    ) -> str:
        executor = getattr(self, "executor", None)
        if executor is None:
            client = getattr(self, "client", None)
            if client is None:
                client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
                self.client = client
            executor = AIExecutor(client)
            self.executor = executor

        return await executor.generate(
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            history=history,
            reasoning_effort=reasoning_effort,
        )

    # ==========================================================================
    # Chat
    # ==========================================================================

    async def chat(
        self,
        user_name: str,
        content: str,
        history=None,
    ):
        selection = await self._policy().select(content)

        regulation_mode = any(
            keyword in content
            for keyword in Config.REGULATION_KEYWORDS
        )

        system_prompt = PromptBuilder.chat_system_prompt(
            regulation_mode=regulation_mode
        )
        user_prompt = PromptBuilder.chat_user_prompt(
            user_name,
            content,
        )

        logger.info(
            "AI route selected | route=%s | source=%s | model=%s | "
            "effort=%s | max_output_tokens=%s | history=%s",
            selection.route,
            selection.source,
            selection.model,
            selection.reasoning_effort,
            selection.max_output_tokens,
            len(history) if history else 0,
        )

        reply = await self.call_gpt(
            system=system_prompt,
            user=user_prompt,
            model=selection.model,
            max_tokens=selection.max_output_tokens,
            history=history,
            reasoning_effort=selection.reasoning_effort,
        )

        return reply, selection.model, selection.route

    # ==========================================================================
    # Fast/specialized tasks - intentionally bypass Jev
    # ==========================================================================

    async def translate(
        self,
        text: str,
        target_language: str,
    ) -> str:
        system, user = PromptBuilder.translation_prompt(
            text,
            target_language,
        )
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.FAST_MODEL,
            max_tokens=1500,
            reasoning_effort=Config.FAST_REASONING_EFFORT,
        )

    async def define_word(
        self,
        word: str,
        wiki_mode: bool = False,
    ) -> str:
        system, user = PromptBuilder.definition_prompt(
            word,
            wiki_mode,
        )
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.FAST_MODEL,
            max_tokens=1000,
            reasoning_effort=Config.FAST_REASONING_EFFORT,
        )

    async def summarize(self, messages) -> str:
        system, user = PromptBuilder.summary_prompt(messages)
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.CHAT_MODEL,
            max_tokens=1000,
            reasoning_effort=Config.CHAT_REASONING_EFFORT,
        )
