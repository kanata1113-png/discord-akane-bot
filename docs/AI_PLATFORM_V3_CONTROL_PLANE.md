# AI Platform v3.0 — Integrated Control Plane

Status: Phase D integration candidate.

## Purpose

v3.0 introduces `AIControlPlane` as the composition root for the AI platform. It wires the provider layer, adaptive acceptance decorator, routing policy, intent/budget controllers, orchestrator and telemetry while leaving Discord/database ownership outside the control plane.

## Integrated flow

```text
Discord
  -> AiManager compatibility facade
  -> AIControlPlane
      -> RouterProvider (Jev in production)
      -> AdaptiveRouterProvider (feature-gated)
      -> RoutingPolicy / continuity floor
      -> AIOrchestrator
          -> OrchestrationContext
          -> IntentController
          -> BudgetController
          -> PromptBuilder
          -> AIExecutor
          -> ResponseGuard
          -> ControlPlaneTelemetry
```

## Production-safety defaults

The integration itself does not enable behavior-changing experimental controls. Existing environment flags remain authoritative:

- `JEV_ROUTER_CONTEXT_HINTS` — existing deployed context hints
- `AI_ADAPTIVE_TOKEN_BUDGET` — legacy adaptive budget
- `AI_INTENT_CONTROLLER=false` by default
- `AI_BUDGET_CONTROLLER_V2=false` by default
- `AI_ADAPTIVE_ROUTING_POLICY=false` by default

With adaptive routing disabled, `AdaptiveRouterProvider` preserves the wrapped provider's acceptance decision.

## Privacy boundary

- control-plane telemetry is metadata-only
- external routing context excludes prior message bodies
- no Discord user/guild/channel identifiers are added to routing/control-plane metrics
- replay evaluation requires operator-owned benchmark text and does not reconstruct production prompts from telemetry

## Phase D validation gate

Before accepting v3.0 in production:

1. integrated PR CI must pass on Python 3.12 and 3.13
2. deploy the single integrated main change
3. verify startup, DB persistence, Discord connectivity and slash-command sync
4. run representative normal/reasoning/deep/follow-up/topic-reset/regulation cases
5. inspect `ROUTING_METRIC` and `CONTROL_PLANE_EVENT` correlation by `event_id`
6. confirm no unexpected routing/budget/controller activation
7. only then consider enabling additional v2.x feature flags
