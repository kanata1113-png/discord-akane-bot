# Release C1 — Leaderboard Strangler Slice

## Scope

This slice starts the post-B2 gradual strangler refactor with the existing
`/leaderboard` command.

The change is intentionally structural:

```text
/leaderboard
→ GeneralCog presentation adapter
→ progression CapabilityDispatcher
→ leaderboard capability handler
→ existing data source
```

## Preserved behavior

- slash command remains `/leaderboard`;
- response remains ephemeral;
- TOP30 limit remains 30;
- existing member filtering and Discord embed rendering remain in GeneralCog;
- existing error message remains unchanged;
- XP identity and persistence semantics are unchanged.

## Non-goals

This slice does not:

- add `leaderboard` to natural-language discovery;
- add direct Candidate Panel execution;
- change Jev behavior;
- change DB/schema;
- change XP or ranking semantics;
- change AI routing;
- touch moderation/admin capabilities;
- combine PR #34.

## Gate

Before merge:

1. Python 3.12 CI PASS.
2. Python 3.13 CI PASS.
3. Existing regression suite PASS.
4. New leaderboard handler/adapter tests PASS.
5. Human approval required before merge.
6. Production deployment requires explicit human approval.
