# Release C3 — Capability Cost Metadata

## Problem

A0 inventory used `AI_GENERATION` as a descriptive risk label, while the A1
runtime deliberately standardized execution-policy risk to:

- `READ_ONLY`
- `WRITE_CONFIRM`
- `MODERATION`
- `ADMIN`

Treating external AI spend as a fifth authorization risk would mix two different
policy dimensions.

## Decision

`CapabilitySpec` now keeps execution risk and external cost separate:

```text
risk                  -> authorization / confirmation policy
incurs_external_cost  -> whether execution can incur external service/model cost
```

The new field defaults to `False`, so all existing capability specs retain their
behavior unchanged.

AI generation capabilities can therefore be modeled as non-destructive
`READ_ONLY` execution while still being visible to future cost-routing and
telemetry policy through `incurs_external_cost=True`.

## Non-goals

This slice does not change:

- model routing;
- cost budgets;
- telemetry semantics;
- natural-language discovery;
- confirmation policy;
- DB/schema;
- Discord command behavior.
