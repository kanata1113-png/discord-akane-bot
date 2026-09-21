# AI Platform Phase C — v2.8 to v2.9

Status: repository development only. No production deployment in this phase.

## v2.8 Adaptive Routing Policy

Introduces a route-specific confidence controller behind `AI_ADAPTIVE_ROUTING_POLICY=false` by default.

Default profile:

- normal-chat: 0.88
- reasoning: 0.82
- deep-reasoning: 0.90
- analytical follow-up discount: 0.02

The controller does not learn online and never mutates configuration. `AdaptiveRouterProvider` decorates an existing provider and preserves the provider's original acceptance result when the controller is disabled.

## v2.9 Observability Foundation

Adds metadata-only `CONTROL_PLANE_EVENT` records tied to the existing routing `event_id`.

Current phases:

- `plan_built`
- `execution_complete`

The event schema contains route, source, intent, pipeline, model, budget metadata, and execution latency. It deliberately excludes message content and Discord/user identity fields.

## Phase D boundary

Phase C does not wire the adaptive provider into production configuration. Phase D will perform the final integration, comprehensive CI/review, production deployment, and Human Verification.
