# Release C4 — AI Capability Strangler

## Scope

Migrates the existing AI-backed slash commands behind CapabilityDispatcher:

- `/translate`
- `/define`
- `/summary`

The Discord adapters retain existing presentation, history collection, file
fallbacks, and error messages. Only the AI invocation path moves behind the
capability layer.

## Cost and risk model

All three capabilities are non-destructive execution-policy `READ_ONLY` but set
`incurs_external_cost=True`.

This keeps authorization policy separate from model/API spend and prevents AI
operations from being incorrectly modeled as writes or admin actions.

## Summary boundary

`/summary` continues to collect the caller's own recent channel messages in the
Discord adapter. The capability handler receives only the already-selected text
sequence and invokes the existing AI summarization API. Discord history access
therefore remains a presentation/input-collection concern rather than being
embedded in the AI domain handler.

## Preserved behavior

- slash names and argument shapes unchanged;
- `/summary back` remains clamped to 1–20;
- existing AI manager/model routing remains authoritative;
- existing >4000-character file fallback retained for translate/define;
- no database/schema changes;
- no natural-language direct execution added;
- no moderation/admin changes.
