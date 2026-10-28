# AKANE TOKEN EFFICIENCY RATIONALIZATION v0.1

Status: IMPLEMENTED FOR PR / PUBLIC DOGFOOD TARGET

## Goal

Reduce repeated input-token cost without changing Akane's model router, capability/authorization model, persistent DB contents, or canonical style specification.

## Invariants

- LIGHT = gpt-6-luna / low
- NORMAL = gpt-6-luna / high
- ADVANCED = gpt-6-terra / medium
- Router behavior and promotion/downgrade rules stay unchanged.
- /data/akane_v26.db and stored conversation-history retention stay unchanged.
- Canonical Akane Style Contract and the three accepted few-shot examples remain the source of truth.
- Optimization applies to runtime prompt rendering, injected history, telemetry, and retry behavior only.
- No Freeze is declared by this change.

## R0 — Baseline

Pre-rationalization runtime characteristics:
- PromptBuilder sent the full canonical style/format contract on every request.
- HistoryOptimizer used a 6,000-character threshold.
- Provider usage telemetry counted model responses but did not separate logical requests from model calls.
- OpenAI SDK retry behavior was implicit.
- MAX_TOKENS incomplete responses were returned without an explicit same-model retry contract.

The old prompt renderer and legacy history algorithm are retained in audit-only paths for deterministic R6 comparison.

## R1 — Metrics v2

CostTelemetry now records metadata only:
- logical request ID
- feature
- model call kind (primary / retry / failover)
- attempt number
- input/output/cached/reasoning tokens
- system/history/user character footprint
- local estimated input tokens
- incomplete reason / error class / HTTP status
- latency

Derived metrics:
- Logical Requests
- Model Calls
- Retry/Failover Calls
- Call Amplification
- Input/Output ratio
- retry/failover input tokens
- per-feature averages
- MAX_TOKENS incomplete count
- same-model MAX_TOKENS retry count

No prompt or user text is stored in CostTelemetry.

## R2 — Baseline Evaluation

A deterministic evaluator compares:
- pre-rationalization canonical runtime prompt vs compact runtime prompt
- legacy 6,000-character history behavior vs new token-budget behavior
- total estimated input footprint

This is a static before/after engineering baseline. Production dogfood metrics continue collecting actual provider usage after deployment.

## R3 — Runtime Prompt Rationalization

AkaneStyleContract now has two renderings:
- render(): human-readable canonical specification
- render_runtime(): compact API prompt

PromptBuilder keeps the canonical pre-rationalization renderer for audit only and uses compact runtime text for provider requests.

Preserved:
- CONVERSATIONAL / INFORMATIONAL / TRANSFORMATION profiles
- accepted three few-shot examples
- emphasis priority
- compact-layout rule
- long-form heading rule
- regulation-mode distinctions

## R4 — History Budget

Database retention is unchanged.

Only the history injected into a model call is capped:
- hard budget: about 2,200 locally estimated tokens
- recent messages: up to 6
- recent-history envelope: 1,750 estimated tokens
- older local memo: up to 450 estimated tokens

The current user message is outside HistoryOptimizer and is never truncated by this policy.

## R5 — Retry Rationalization

The OpenAI SDK internal retry layer is disabled so call amplification is observable.

Explicit policy:
- 429 / 500 / 502 / 503 / 504: maximum one same-model retry
- timeout: no automatic repeat
- incomplete MAX_TOKENS: zero same-model retries; return partial output plus existing continuation notice
- other failures: no automatic repeat

Operational target:
- Call Amplification <= 1.2x direction after sufficient dogfood traffic
- same-model MAX_TOKENS retry = 0

## R6 — Before / After Acceptance

Deterministic evaluator acceptance requires:
- compact runtime prompt smaller than canonical baseline
- injected history <= 2,200 estimated tokens
- representative total input footprint lower than baseline
- MAX_TOKENS same-model retry disabled
- nominal no-error Call Amplification = 1.0
- operational dogfood target = <= 1.2x

Human-quality acceptance remains a dogfood check: no perceived regression in Akane persona, answer correctness, or continuity.

## Production Verification

After merge:
1. GitHub CI must pass on Python 3.12 and 3.13.
2. Railway deployment must reach SUCCESS.
3. Startup must retain DB schema 2 and existing persistent volume.
4. GPT routing tiers must remain Luna/low, Luna/high, Terra/medium.
5. /admin ai_usagedashboard must expose Token Efficiency metrics.

