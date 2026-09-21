# Release D — Waterfall Integration Gate

Authoritative aggregate for the first WRITE_CONFIRM natural-language execution batch.

## Included slices

- D1 local write-intent classification
- D2 requester-only write interaction primitives
- D3 Candidate Panel handoff into WRITE_CONFIRM flow
- D4 write-aware local discovery ranking
- D5 Release D discovery catalog
- D6 production message-discovery activation through the existing integration point
- D7 regression tests for write discovery and direct-execution separation
- D8 architecture / safety contract
- D9 cross-layer discovery policy audit
- D10 aggregate integration gate

## Non-negotiable invariants

- `title_set`, `memory_forget`, and `remind` are discoverable but never direct-executable.
- Candidate selection alone never mutates state.
- Final write execution reuses the existing GeneralCog slash callbacks and CapabilityDispatcher paths.
- Requester-only checks apply throughout the write UI.
- Cancellation performs no write and does not resume the consumed AI-chat turn.
- Moderation/admin capabilities remain excluded.
- No DB/schema, XP, AI routing, Jev authority, or persistent-view contract changes.

## Human verification boundary

After CI + production boot, verify the three WRITE_CONFIRM flows plus cancellation and ordinary-chat false-positive behavior before expanding Release D further.
