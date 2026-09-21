# AI Platform Phase A — v2.1 to v2.4

Status: repository development track. No production deployment is implied by this document.

## v2.1 Orchestrator Hardening

`AIOrchestrator` now exposes explicit stages:

1. `prepare_context`
2. `classify_intent`
3. `select_route`
4. `select_budget`
5. `build_prompts`
6. `build_plan`
7. `execute`

The public `chat()` compatibility contract remains `(reply, model, route)`.

## v2.2 Unified Routing Context

`OrchestrationContext` is the local request object. It may contain the current message body because it never leaves the process by itself.

`ExternalRoutingContext` is a privacy-minimal projection containing only routing metadata such as history counts, follow-up state, intent, message length, continuity labels and requested format. Prior message bodies are intentionally excluded.

## v2.3 Intent Controller

`IntentController` maps deterministic intent hints to candidate pipelines. It is gated by:

```text
AI_INTENT_CONTROLLER=false
```

by default.

Only `general-chat` is currently registered in the orchestrator. Therefore enabling the controller alone cannot silently redirect translation, definition or summary requests into incomplete pipelines; unregistered intents fall back to general chat.

## v2.4 Budget Controller

`BudgetController` adds context-aware output-budget decisions while preserving existing hard caps. It is separately gated by:

```text
AI_BUDGET_CONTROLLER_V2=false
```

This is intentionally separate from the existing `AI_ADAPTIVE_TOKEN_BUDGET` feature flag so Phase A can be evaluated without changing the already-deployed v1 budget policy.

The controller can account for requested detail/shortness and deterministic intent while never exceeding route hard caps.

## Safety invariants

- no DB/schema changes
- no Discord command changes
- no changes to XP, memory, tickets or persistent views
- no prior history bodies in external routing context
- existing Jev/Legacy continuity floor remains inside `RoutingPolicy`
- existing specialized AiManager methods remain unchanged
- new intent and v2 budget controllers default to disabled

## Verification gate

Phase A should pass the existing characterization suite on Python 3.12 and 3.13 before it is merged into `main`. Human verification is intentionally deferred until the later integrated validation phase approved for the roadmap.
