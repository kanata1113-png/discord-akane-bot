# AI Platform Phase B — v2.5 to v2.7

Status: repository development only. No production deployment in this phase.

## v2.5 Response Guard v2

Extends deterministic mechanical response checks with unclosed code-fence and explicitly requested structure checks. It does not score truth, politics, style, or general semantic quality.

## v2.6 Evaluation / Replay Framework

Two deliberately separate mechanisms are provided:

- `RoutingBenchmarkCase` contains explicit operator-owned prompt fixtures and can actually re-run RoutingPolicy.
- `TelemetryReplayEvent` contains metadata-only production telemetry and can be aggregated, but cannot reconstruct or re-run the original prompt because message bodies are intentionally absent.

This separation prevents the evaluation layer from quietly weakening the production privacy boundary.

## v2.7 Provider Abstraction

`RoutingPolicy` now depends on the structural `RouterProvider` / `RouteDecision` protocol rather than Jev-specific classes. `JevModelRouter` remains the production provider and is behaviorally unchanged.

## Compatibility

- no database/schema changes
- no Discord command changes
- no Railway changes
- no feature activation
- continuity floor behavior remains in RoutingPolicy
- legacy, shadow and production modes retain their existing semantics
