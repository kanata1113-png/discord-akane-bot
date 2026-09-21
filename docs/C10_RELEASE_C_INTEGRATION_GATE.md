# Release C10 — Integration Gate

## Batch boundary

C10 closes the first Release C waterfall batch spanning PR #50 through #59.
The gate verifies the combined architecture rather than treating each migration
slice as an isolated endpoint.

## Machine-checked contracts

1. General slash-command surface remains identical to the legacy GeneralCog.
2. Migrated capability IDs are unique.
3. Release C discovery is a subset of the migrated capability catalog.
4. WRITE_CONFIRM capabilities are absent from discovery and direct execution.
5. AI capabilities expose external-cost metadata but remain selection-only.
6. Direct execution is a subset of discovery.
7. The exact direct-execution allowlist is frozen to:
   - level
   - leaderboard
   - weekly
   - profile
   - achievements
   - memory_status
8. Cross-layer discovery-policy audit passes.

## Human Verification boundary

After the stacked CI sequence is green and the batch is merged/deployed under
normal release approval, Human Verification should test representative flows,
not every internal PR separately:

- inherited/unmigrated slash command still works;
- migrated read command works;
- migrated write slash command preserves behavior;
- expanded discovery finds new candidates;
- leaderboard and memory status direct-execute after explicit selection;
- AI candidates remain selection-only;
- unsupported write-shaped natural language does not misroute to read candidates;
- cancellation remains terminal and non-executing.

## Non-goals

No moderation/admin natural-language execution, no DB/schema migration, no XP
semantic change, and no AI model-routing change are part of this batch.
