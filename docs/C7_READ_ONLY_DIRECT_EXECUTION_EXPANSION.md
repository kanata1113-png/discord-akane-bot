# Release C7 — Read-Only Direct Execution Expansion

## Scope

Expands explicit-selection direct execution by two capabilities:

- `leaderboard` → `/leaderboard`
- `memory_status` → `/memory`

Both require no additional user argument after Candidate Panel selection and do
not intentionally mutate persistent state.

## Exact allowlist

```text
level
leaderboard
weekly
profile
achievements
memory_status
```

The allowlist remains exact and fail-closed.

## Explicit exclusions

- `rankings`: requires a category argument.
- `fortune`: first access persists fortune/count state.
- `titles`: unlock evaluation may persist bookkeeping.
- `translate`, `define`, `summary`: require arguments and incur external cost.
- `remind`, `memory_forget`, `title_set`: WRITE_CONFIRM.
- moderation/admin/unknown: never direct-executed by this path.

## Adapter mapping

Most capability IDs equal their GeneralCog command attribute. `memory_status`
intentionally maps to the existing `/memory` adapter through an explicit alias.
No heuristic command lookup is introduced.

## Invariants

- requester selection remains mandatory;
- Candidate Panel cancellation remains terminal and non-executing;
- DB/schema, AI routing and XP semantics are unchanged;
- no write capability gains direct-execution authority.
