# Akane AI Platform v1.8 Development Track

Status: repository-only development. **Do not deploy from this branch.**

## Included milestones

### v1.1 Routing Calibration

`ROUTING_METRIC` now includes an ephemeral `event_id` plus optional privacy-minimal context and budget fields. The offline analyzer reports confidence buckets, Jev/Legacy disagreements, promotions/demotions, model mix, fallback reasons and latency distribution.

No Discord identity or message history is added to telemetry.

### v1.3 Privacy-minimal Context Hints

`ContextBuilder` derives only:

- usable history count
- prior user/assistant message counts
- whether the current message looks like a follow-up

Prior message bodies are never included in the routing hint.

Feature flag:

```text
JEV_ROUTER_CONTEXT_HINTS=false
```

Default is `false`, preserving v1.0 behavior.

### v1.6 Adaptive Token Budget

`TokenBudgetPolicy` can reduce output ceilings for short requests while never exceeding the existing v1.0 route caps.

Feature flag:

```text
AI_ADAPTIVE_TOKEN_BUDGET=false
```

Default is `false`.

### v1.7 Offline Evaluation Baseline

Run:

```bash
python tools/evaluate_legacy_router.py
```

This characterizes deterministic Legacy routing without calling Jev or OpenAI.

### v1.8 Multi-router Preparation

`RouterProvider` defines the structural provider contract. `JevModelRouter` already conforms to it, allowing future experimental providers without coupling them to Discord-facing code.

## Safety boundary

The development branch intentionally keeps all new behavioral features opt-in. A future merge alone must not activate context hints or adaptive token budgets in production.

Production activation requires a separate reviewed configuration change after benchmark/human verification.
