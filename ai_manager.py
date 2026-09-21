import logging

from openai import AsyncOpenAI

from config import Config
from services.adaptive_router_provider import AdaptiveRouterProvider
from services.ai_executor import AIExecutor
from services.ai_orchestrator import AIOrchestrator
from services.jev_model_router import JevModelRouter
from services.prompt_builder import PromptBuilder
from services.routing_metrics import RoutingTelemetry
from services.routing_policy import RoutingPolicy


logger = logging.getLogger("AkaneBot")


class AiManager:
    """Compatibility facade for Akane's AI control plane."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        self.executor = AIExecutor(self.client)
        base_router = JevModelRouter.from_environment()
        self.jev_router = AdaptiveRouterProvider(base_router)
        self.routing_telemetry = RoutingTelemetry()
        self.routing_policy = RoutingPolicy(
            self.jev_router,
            telemetry=self.routing_telemetry,
        )
        self.orchestrator = AIOrchestrator(
            self.routing_policy,
            self.call_gpt,
        )

        logger.info(
            "AI platform initialized | version=3.0-candidate | "
            "jev_mode=%s | jev_configured=%s | "
            "confidence_threshold=%.2f | timeout_seconds=%.2f | "
            "context_hints=%s | adaptive_budget_v1=%s | "
            "intent_controller=%s | budget_controller_v2=%s | "
            "adaptive_routing_policy=%s",
            self.jev_router.mode,
            self.jev_router.is_configured,
            self.jev_router.confidence_threshold,
            self.jev_router.timeout_seconds,
            self.routing_policy.context_hints_enabled,
            self.routing_policy.adaptive_budget_enabled,
            self.orchestrator.intent_controller.enabled,
            self.orchestrator.budget_controller.enabled,
            self.jev_router.adaptive_policy_enabled,
        )

    def _policy(self) -> RoutingPolicy:
        policy = getattr(self, "routing_policy", None)
        router = getattr(self, "jev_router", None)
        if router is None:
            router = AdaptiveRouterProvider(JevModelRouter.from_environment())
            self.jev_router = router
        if policy is None or policy.jev_router is not router:
            telemetry = getattr(self, "routing_telemetry", None)
            policy = RoutingPolicy(router, telemetry=telemetry)
            self.routing_policy = policy
        return policy

    def _orchestrator(self) -> AIOrchestrator:
        policy = self._policy()
        orchestrator = getattr(self, "orchestrator", None)
        if (
            orchestrator is None
            or orchestrator.routing_policy is not policy
            or orchestrator.generate != self.call_gpt
        ):
            orchestrator = AIOrchestrator(policy, self.call_gpt)
            self.orchestrator = orchestrator
        return orchestrator

    @staticmethod
    def get_system_prompt(regulation_mode: bool = False) -> str:
        return PromptBuilder.chat_system_prompt(regulation_mode=regulation_mode)

    def select_chat_model(self, content: str) -> tuple[str, str, str]:
        selection = RoutingPolicy.legacy_selection(content)
        return selection.model, selection.reasoning_effort, selection.route

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

    async def _run_jev_shadow(self, content: str, legacy_route: str) -> None:
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

    def _schedule_jev_shadow(self, content: str, legacy_route: str) -> None:
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
        selection = await self._policy().select(content)
        return selection.model, selection.reasoning_effort, selection.route

    @staticmethod
    def select_chat_max_tokens(route: str) -> int:
        return RoutingPolicy.tier_for_route(route).max_output_tokens

    async def call_gpt(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        history=None,
        reasoning_effort: str = "low",
        requested_format: str | None = None,
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
            requested_format=requested_format,
        )

    async def chat(self, user_name: str, content: str, history=None):
        return await self._orchestrator().chat(
            user_name=user_name,
            content=content,
            history=history,
        )

    async def translate(self, text: str, target_language: str) -> str:
        system, user = PromptBuilder.translation_prompt(text, target_language)
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.FAST_MODEL,
            max_tokens=1500,
            reasoning_effort=Config.FAST_REASONING_EFFORT,
        )

    async def define_word(self, word: str, wiki_mode: bool = False) -> str:
        system, user = PromptBuilder.definition_prompt(word, wiki_mode)
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
