# Akane AI Platform v1.0 Candidate

## Status

Repository-only development candidate. Not deployed.

## Goals

- Use Jev only for chat model-tier routing.
- Keep specialized commands such as translation, dictionary and summary outside Jev.
- Fail safely to the deterministic Legacy router.
- Preserve regulation/free-speech prompt augmentation independently from model routing.
- Keep routing telemetry privacy-minimal and useful for calibration.
- Separate routing, prompt construction and OpenAI execution so each layer can evolve independently.

## Architecture

```text
Discord
  |
  v
AiManager facade
  |
  +--> RoutingPolicy
  |      +--> Legacy baseline
  |      +--> Jev router
  |      +--> fallback policy
  |      +--> model / effort / token budget
  |      `--> RoutingTelemetry
  |
  +--> PromptBuilder
  |
  `--> AIExecutor --> OpenAI Responses API
```

## Routing modes

`JEV_ROUTER_MODE` controls chat routing.

- `legacy` — Jev is bypassed. This is the safe default.
- `shadow` — Legacy remains authoritative and Jev observes asynchronously.
- `production` — Accepted Jev decisions select the model tier; rejected or failed decisions fall back to Legacy.

Invalid or missing mode values resolve to `legacy`.

## Model tiers

| Route | Model | Reasoning effort | Output budget |
| --- | --- | --- | ---: |
| `normal-chat` | `Config.CHAT_MODEL` | low | 1500 |
| `reasoning` | `Config.REASONING_MODEL` | medium | 2000 |
| `deep-reasoning` | `Config.REASONING_MODEL` | configured deep effort | 3000 |

Legacy-only `regulation` and `long-question` routes map to the reasoning tier.

## Jev acceptance and fallback

The confidence threshold is controlled by `JEV_ROUTER_CONFIDENCE` and defaults to `0.85`.

The default Jev timeout is `1.5` seconds through `JEV_ROUTER_TIMEOUT_SECONDS`.

Production falls back to Legacy for:

- missing API key/configuration
- low confidence
- invalid route
- timeout/network/API error
- unavailable router

## Prompt safety boundary

Routing and prompt augmentation are intentionally separate.

A regulation/free-speech message can be routed by Jev to any model tier while still receiving the regulation-specific system-prompt section. This prevents model selection from silently changing domain behavior.

## Telemetry

Routing telemetry is emitted as structured `ROUTING_METRIC` JSON log lines.

It may contain:

- mode
- source (`jev` or `legacy`)
- legacy route
- selected route
- Jev route
- confidence
- latency
- fallback reason
- selected model
- reasoning effort
- output budget

It intentionally excludes:

- message content
- username
- Discord user ID
- guild ID
- channel ID
- conversation history

Use:

```bash
python tools/analyze_routing_metrics.py railway.log
```

to summarize exported logs offline.

## Compatibility

`AiManager` remains the Discord-facing compatibility facade. Existing callers can continue using:

- `chat()`
- `translate()`
- `define_word()`
- `summarize()`
- `call_gpt()`
- legacy routing helper methods used by characterization tests

No database schema changes are introduced by this AI platform work.

## Deployment gate

Before production deployment:

1. CI must pass on Python 3.12 and 3.13.
2. Review the final diff against the current production branch.
3. Merge only after explicit approval.
4. Set Railway `JEV_ROUTER_MODE=production` only when production routing is intended.
5. Verify startup logs report the expected mode, configuration state, threshold and timeout.
6. Run human verification with normal, reasoning, deep-reasoning and regulation examples.
7. If routing quality or latency is unacceptable, switch `JEV_ROUTER_MODE=legacy` without a code rollback.

## Post-launch calibration

Collect privacy-minimal routing metrics before changing thresholds. Evaluate Jev disagreements using human judgment rather than treating Legacy as ground truth. Tune confidence/timeout only after enough real traffic exists to support the change.
