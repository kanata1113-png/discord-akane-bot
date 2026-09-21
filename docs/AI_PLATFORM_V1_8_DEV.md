# Akane AI Platform v1.8 Development Track

Status: v1.8 baseline merged to `main`; this document also records follow-up hardening work.

## Included milestones

### v1.1 Routing Calibration

`ROUTING_METRIC` includes an ephemeral `event_id` plus privacy-minimal context, intent, relative-cost and budget fields. The offline analyzer reports confidence buckets, Jev/Legacy disagreements, promotions/demotions, model mix, fallback reasons, relative-cost units and latency distribution.

No Discord identity or prior message body is added to telemetry.

### v1.2 Cost-aware Foundation

`CostPolicy` estimates **relative cost units** from model tier and output budget. These values are deliberately not presented as provider prices and do not alter routing yet. They create a calibration surface for later cost-aware decisions.

### v1.3 Privacy-minimal Context Hints

`ContextBuilder` derives usable history count, prior role counts, and whether the current message looks like a follow-up. Prior message bodies are never included in the routing hint.

Feature flag:

```text
JEV_ROUTER_CONTEXT_HINTS=false
```

Default is `false` unless explicitly enabled in deployment configuration.

### v1.3.1 Context Continuity Hardening

Production verification of v1.3 showed two limits: a standalone analysis request could be falsely marked as a follow-up, and a true follow-up such as `それをもう少し詳しく` did not tell Jev what routing tier the prior turn had used.

v1.3.1 therefore:

- narrows follow-up markers to expressions that actually reference prior context
- removes generic task markers such as `比較して` and `詳しく`
- derives `previous_route` and `previous_intent` locally from the most recent prior user turn
- sends those derived labels only when the current message is a detected follow-up
- never sends the prior message body to Jev
- records the derived labels in privacy-minimal routing telemetry for verification

Example routing hint:

```text
routing_context=history:12,prior_user:6,prior_assistant:6,followup:true,previous_route:reasoning,previous_intent:analysis
```

### v1.4 Intent Gate — Observational

`IntentGate` classifies chat into coarse hints such as `casual-chat`, `question`, `analysis`, `translation-like`, `summary-like`, and `definition-like`.

This is telemetry-only in v1.4. It does **not** redirect ordinary chat into slash-command pipelines.

### v1.5 Response Quality Guard

`ResponseGuard` performs deterministic checks for empty, mechanically too-short, and incomplete responses. It does not use another LLM and does not judge factual quality. Integration is diagnostic/logging only, preserving existing reply behavior.

### v1.6 Adaptive Token Budget

`TokenBudgetPolicy` can reduce output ceilings for short requests while never exceeding the existing route caps.

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

Context hints and adaptive token budgets remain independently controlled. `AI_ADAPTIVE_TOKEN_BUDGET` should remain disabled until separate output-quality verification is complete.
