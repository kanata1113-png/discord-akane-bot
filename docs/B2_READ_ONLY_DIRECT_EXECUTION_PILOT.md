# B2 Read-Only Direct Execution Pilot

## Status

Release B final execution slice after Candidate Panel human verification.

The natural-language discovery pipeline may now execute a capability only after
the requester explicitly presses that capability's Candidate Panel button.
Cancellation, timeout, discovery rejection, and ordinary AI chat remain separate
paths.

## Approved direct-execution set

- `level`
- `weekly`
- `profile`
- `achievements`

These capabilities reuse their existing `GeneralCog` slash-command callbacks.
Those callbacks already dispatch through the existing progression
`CapabilityDispatcher`, preserving the current Discord rendering and domain/data
behavior rather than reimplementing it in discovery.

## Explicit exclusions

### `rankings`

Not directly executed in this pilot. `/rankings` requires an explicit `category`
argument (`weekly`, `messages`, `ai`, or `achievements`). Candidate discovery
selects only the capability and does not carry that required argument. The pilot
therefore fails closed and points the user to `/rankings` rather than inferring a
category.

### `fortune`

Not directly executed in this pilot. First access can persist the daily fortune
and increment fortune state, so it remains outside the read-only natural-language
execution allowlist pending a separate policy decision.

### moderation / admin / unknown capabilities

Never directly executed. The allowlist is exact and fails closed.

## Interaction boundary

```text
natural-language message
→ local gate
→ local shortlist
→ optional Jev rerank
→ Candidate Panel
→ requester explicitly selects a candidate
   ├─ approved direct-execution capability
   │  → existing GeneralCog command callback
   │  → existing CapabilityDispatcher
   │  → existing response behavior
   └─ excluded / unknown capability
      → no execution; show existing slash command guidance
```

The Candidate Panel still owns no database reference or CapabilityDispatcher.

## Cancellation boundary

`キャンセル` remains distinct from selection and timeout:

- requester-only;
- sets `cancelled=True`;
- keeps `selection=None`;
- invokes no execution callback;
- disables every control;
- does not fall back to AI chat;
- ends processing for that message.

## Invariants

This slice does not change:

- DB schema;
- XP semantics;
- progression persistence semantics;
- AI routing semantics;
- Jev reranking semantics;
- slash command names or parameters;
- moderation/admin capability policy.
