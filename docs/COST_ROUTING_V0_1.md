# Cost Routing v0.1 — Luna / Terra / Sol

Status: repository candidate. Not production-deployed by this document alone.

## Goal

Reduce unnecessary Sol usage while preserving the existing Jev route taxonomy, continuity behavior, telemetry, and replay compatibility.

Target model distribution after later calibration:

- Luna: 50–70%
- Terra: 20–40%
- Sol: 10–20%

These are operating targets, not hard per-window quotas.

## Model assignment

The current route labels remain unchanged, but their model tiers become:

```text
normal-chat                    -> gpt-5.6-luna
reasoning / regulation /
long-question                  -> gpt-5.6-terra
deep-reasoning                 -> gpt-5.6-sol
```

Interpretation:

- Luna is the default tier.
- Terra handles standard structured/analytical work.
- Sol is an explicit promotion tier for genuinely difficult reasoning.

## Why preserve route labels

Changing Jev's output taxonomy at the same time as changing model tiers would mix two independent variables. v0.1 therefore keeps `normal-chat`, `reasoning`, and `deep-reasoning` semantics stable and changes only model assignment.

This preserves:

- Jev integration
- continuity-floor metadata
- routing telemetry
- replay/evaluation fixtures
- fallback behavior

## Continuity behavior

A reasoning continuity floor now preserves the `reasoning` route but maps it to Terra instead of automatically keeping Sol.

Only a `deep-reasoning` continuity anchor retains Sol.

This directly addresses the observed cost amplification where a single analytical Sol turn could keep simple follow-ups on Sol.

## Non-goals in v0.1

- no hard 10–20% Sol quota
- no online learning
- no self-modifying thresholds
- no change to DB/schema
- no change to Discord commands
- no automatic production deployment

A later Cost Optimization Gate should benchmark explicit Sol promotion criteria and verify quality before broad production activation.
