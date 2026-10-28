import logging

from openai import AsyncOpenAI

from config import Config
from services.ai_control_plane import AIControlPlane
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
        self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY, max_retries=0)
        self.executor = AIExecutor(self.client)
        self.routing_telemetry = RoutingTelemetry()
        self.control_plane = AIControlPlane.from_environment(
            generate=self.call_gpt,
            routing_telemetry=self.routing_telemetry,
        )
        # Keep stable runtime handles used by current call sites and tests.
        self.jev_router = self.control_plane.provider
        self.routing_policy = self.control_plane.routing_policy
        self.orchestrator = self.control_plane.orchestrator

        snapshot = self.control_plane.snapshot()
        confidence_threshold = self.jev_router.confidence_threshold
        timeout_seconds = self.jev_router.timeout_seconds
        logger.info(
            "AI platform initialized | version=%s | "
            "jev_mode=%s | jev_configured=%s | "
            "confidence_threshold=%s | timeout_seconds=%s | "
            "context_hints=%s | adaptive_routing=%s | "
            "adaptive_budget_v1=%s | intent_controller=%s | "
            "budget_controller_v2=%s",
            snapshot.version,
            snapshot.router_mode,
            snapshot.router_configured,
            confidence_threshold,
            timeout_seconds,
            snapshot.context_hints_enabled,
            snapshot.adaptive_routing_enabled,
            snapshot.adaptive_budget_v1_enabled,
            snapshot.intent_controller_enabled,
            snapshot.budget_controller_v2_enabled,
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

    async def call_gpt(
        self,
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
        executor = getattr(self, "executor", None)
        if executor is None:
            client = getattr(self, "client", None)
            if client is None:
                client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY, max_retries=0)
                self.client = client
            executor = AIExecutor(client)
            self.executor = executor

        effective_route = route if route != "unknown" else RoutingPolicy.legacy_route(user)
        return await executor.generate(
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            history=history,
            reasoning_effort=reasoning_effort,
            route=effective_route,
            feature=feature,
            logical_request_id=logical_request_id,
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
            feature="translation",
        )

    async def define_word(self, word: str, wiki_mode: bool = False) -> str:
        system, user = PromptBuilder.definition_prompt(word, wiki_mode)
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.FAST_MODEL,
            max_tokens=1000,
            reasoning_effort=Config.FAST_REASONING_EFFORT,
            feature="definition",
        )

    async def summarize(self, messages) -> str:
        system, user = PromptBuilder.summary_prompt(messages)
        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.CHAT_MODEL,
            max_tokens=1000,
            reasoning_effort=Config.CHAT_REASONING_EFFORT,
            feature="summary",
        )
