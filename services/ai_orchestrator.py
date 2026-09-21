from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from services.budget_controller import BudgetController, BudgetDecision
from services.intent_controller import IntentController, IntentDecision
from services.orchestration_context import (
    OrchestrationContext,
    OrchestrationContextBuilder,
)
from services.prompt_builder import PromptBuilder
from services.routing_policy import RouteSelection, RoutingPolicy


logger = logging.getLogger("AkaneBot")

GenerateCallable = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class OrchestrationPlan:
    context: OrchestrationContext
    intent: IntentDecision
    route: RouteSelection
    budget: BudgetDecision
    system_prompt: str
    user_prompt: str


class AIOrchestrator:
    """Coordinates request context, intent, routing, budget and execution.

    Phase A makes each orchestration stage explicit while preserving the
    existing general-chat behavior by default. New intent and v2 budget
    controllers are independently feature-gated.
    """

    def __init__(
        self,
        routing_policy: RoutingPolicy,
        generate: GenerateCallable,
        *,
        intent_controller: IntentController | None = None,
        budget_controller: BudgetController | None = None,
    ) -> None:
        self.routing_policy = routing_policy
        self.generate = generate
        self.intent_controller = intent_controller or IntentController()
        self.budget_controller = budget_controller or BudgetController()

    def prepare_context(
        self,
        *,
        content: str,
        history=None,
    ) -> OrchestrationContext:
        return OrchestrationContextBuilder.build(content, history)

    def classify_intent(self, context: OrchestrationContext) -> IntentDecision:
        # Only general-chat is currently registered as an execution pipeline.
        # Specialized handlers remain on AiManager until a later migration.
        return self.intent_controller.decide(
            context,
            supported_pipelines={"general-chat"},
        )

    async def select_route(self, *, content: str, history=None) -> RouteSelection:
        return await self.routing_policy.select(content, history=history)

    def select_budget(
        self,
        *,
        route: RouteSelection,
        context: OrchestrationContext,
    ) -> BudgetDecision:
        decision = self.budget_controller.decide(route.route, context)
        if not decision.controller_enabled:
            return BudgetDecision(
                route=route.route,
                max_output_tokens=route.max_output_tokens,
                hard_cap=decision.hard_cap,
                reason=route.budget_reason or "routing_policy_budget",
                controller_enabled=False,
            )
        return decision

    def build_prompts(
        self,
        *,
        user_name: str,
        content: str,
        context: OrchestrationContext,
    ) -> tuple[str, str]:
        return (
            PromptBuilder.chat_system_prompt(
                regulation_mode=context.regulation_mode,
            ),
            PromptBuilder.chat_user_prompt(user_name, content),
        )

    async def build_plan(
        self,
        *,
        user_name: str,
        content: str,
        history=None,
    ) -> OrchestrationPlan:
        context = self.prepare_context(content=content, history=history)
        intent = self.classify_intent(context)
        route = await self.select_route(content=content, history=history)
        budget = self.select_budget(route=route, context=context)
        system_prompt, user_prompt = self.build_prompts(
            user_name=user_name,
            content=content,
            context=context,
        )
        return OrchestrationPlan(
            context=context,
            intent=intent,
            route=route,
            budget=budget,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def execute(self, plan: OrchestrationPlan, *, history=None) -> str:
        return await self.generate(
            system=plan.system_prompt,
            user=plan.user_prompt,
            model=plan.route.model,
            max_tokens=plan.budget.max_output_tokens,
            history=history,
            reasoning_effort=plan.route.reasoning_effort,
        )

    async def chat(
        self,
        *,
        user_name: str,
        content: str,
        history=None,
    ) -> tuple[str, str, str]:
        plan = await self.build_plan(
            user_name=user_name,
            content=content,
            history=history,
        )

        logger.info(
            "AI orchestration | route=%s | source=%s | model=%s | "
            "effort=%s | max_output_tokens=%s | intent=%s | pipeline=%s | "
            "budget_reason=%s | history=%s | event_id=%s",
            plan.route.route,
            plan.route.source,
            plan.route.model,
            plan.route.reasoning_effort,
            plan.budget.max_output_tokens,
            plan.intent.intent,
            plan.intent.effective_pipeline,
            plan.budget.reason,
            len(history) if history else 0,
            plan.route.event_id,
        )

        reply = await self.execute(plan, history=history)
        return reply, plan.route.model, plan.route.route
