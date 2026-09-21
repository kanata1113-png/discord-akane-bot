# AI Platform v3.1 — Cost & Context Optimization

## Goals

Reduce everyday input/output cost without making routing opaque or sacrificing completion reliability.

## Production controls in this release

### 1. Local history optimization

- Routing still sees the original history metadata.
- Execution history is compressed only when it exceeds 6000 characters and more than six usable messages exist.
- The newest six messages are preserved verbatim.
- Older messages are locally reduced to a bounded memo; no extra LLM/API call is used.
- Logs expose only character counts and mode, not message bodies.

### 2. Lightweight follow-up downgrade

Short follow-ups such as "それを短く、要点だけ" can move one tier down when safe:

- Sol → Terra
- Terra → Luna

Regulation-mode and detailed follow-ups are protected from this downgrade.

### 3. Adaptive output budget

Default/compact requests use small deterministic adjustments based on request length. Expanded Terra keeps the 2000-token completion cap established after production truncation was observed.

### 4. Sol Promotion Gate v0.3

Sol promotion uses a deterministic score:

- explicit depth markers: +2 each
- structural complexity markers: +1 each, capped at three
- long request bonuses: +1 at 120 chars, +1 at 400 chars
- Sol threshold: 3

This remains a safety gate, not an autonomous learning system.

### 5. Cost telemetry v0.3

Metadata-only telemetry now includes:

- actual input/output/cached/reasoning tokens when exposed by Responses API
- route and model
- latency
- completion state
- rolling model shares
- average input/output tokens
- average latency
- completion rate
- cache rate
- relative cost units

No prompt body, Discord user ID, channel ID, or guild ID is stored in this telemetry.

### 6. Offline calibration/evaluation

`benchmarks/routing_calibration_v02.py` compares Jev confidence thresholds without changing production settings.

`benchmarks/quality_cost_evaluator_v01.py` keeps route match, completion, latency, cost, and optional human quality as separate auditable components instead of collapsing them into an opaque score.

## Explicit non-goals

- no autonomous threshold mutation
- no hidden user preference inference
- no database reset/migration
- no semantic summary API call for history compression
- no hard Sol quota
- no assumption that lower cost means higher quality
