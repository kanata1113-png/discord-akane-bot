# Release C8 — Discovery / Execution Policy Audit

## Purpose

Release C now has three distinct concepts:

1. capability exists in the runtime catalog;
2. capability may appear as a natural-language discovery candidate;
3. capability may execute immediately after explicit Candidate Panel selection.

This slice makes the boundaries machine-checkable.

## Important correction

`profile` and `achievements` were already approved in the B2 direct-execution
pilot, but their legacy handlers may persist unlock bookkeeping. They therefore
must not be described as pure reads.

C8 records them explicitly as:

```text
legacy_b2_bookkeeping_exception
```

New Release C additions (`leaderboard`, `memory_status`) remain ordinary
argument-free, non-external-cost direct execution.

## Selection-only reasons

- `rankings`: required argument
- `fortune`: first-read persistence
- `titles`: unlock bookkeeping
- `translate`, `define`, `summary`: required arguments + external cost

## Validation

`validate_discovery_policy()` fails if:

- a direct-execution ID is absent from the discovery catalog;
- a non-READ_ONLY capability becomes direct-executable;
- an external-cost capability becomes direct-executable;
- the selection-only set drifts without an explicit policy update.

This is a structural gate only; it changes no user-visible behavior.
