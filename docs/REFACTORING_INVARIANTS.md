# Akane Bot v4 — Refactoring Invariants

Baseline: `main@7b93abaeb16ef3f57e1cc9808297c8583864b0ac`

These are behavior and safety contracts for the v4 strangler migration. A refactor that violates an invariant is a behavior change and must be handled explicitly rather than hidden inside structural work.

## 1. Release discipline

- v4 changes are developed on feature branches.
- No direct writes to `main`.
- No merge without explicit human approval.
- No Railway deployment without explicit human approval.
- PR #34 / Discord-native Markdown v0.2 remains independent from v4 architecture work unless explicitly combined.
- Prefer extraction/adapters to wholesale rewrites.

## 2. Slash-command compatibility

- Existing slash command names remain supported.
- Existing argument shapes remain compatible unless a dedicated behavior change is approved.
- Natural-language discovery is an additional entry point, not a replacement.
- A migrated slash command and natural-language action must converge on the same capability handler rather than duplicate business logic.
- The `/admin` authorization boundary must not be weakened.

## 3. AI routing invariants

Capability work must not incidentally change:

- Luna/Terra/Sol role assignment;
- reasoning-effort configuration;
- legacy/Jev route selection semantics;
- confidence fallback behavior;
- continuity behavior;
- follow-up downgrade;
- Sol promotion;
- output budgets;
- history optimization;
- prompt construction;
- response guard;
- cost/routing telemetry meaning.

A future Capability Router is separate from the existing **AI model router**. The names and telemetry must make that distinction clear.

## 4. Jev authority invariant

Jev may classify, rank, or extract candidate arguments. Jev must not become an authorization layer.

It may not:

- bypass Discord permissions;
- write directly to SQLite;
- execute moderation/admin actions directly;
- turn low-confidence classification into silent execution.

Future execution path:

```text
Jev candidate
→ local validation
→ permission/risk policy
→ user selection/confirmation
→ capability dispatcher
→ handler
```

## 5. XP invariants

Preserve current production semantics, including:

- global user XP identity;
- configured XP-per-message value;
- configured cooldown;
- current level requirement calculation;
- leftover-XP behavior;
- existing level reward behavior unless explicitly migrated.

Capability refactoring must not silently make XP guild-scoped.

## 6. Weekly XP invariants

- Weekly XP remains guild-scoped.
- Week calculation retains current JST semantics.
- Existing ranking behavior and limits remain compatible.
- Natural-language discovery does not redefine ranking categories.

## 7. Fortune invariants

- Fortune remains deterministic for the current guild/user/JST-date contract.
- Preserve the existing seed behavior.
- Repeated same-day access must retain current behavior.
- Existing fortune count/progression bookkeeping is preserved during handler extraction.

## 8. Progression invariants

- Existing achievements and titles remain compatible.
- Existing equipped-title behavior remains compatible.
- Existing unlock evaluation side effects must be characterized before extraction.
- Do not "clean up" duplicate notification behavior inside an unrelated capability PR; record and fix it separately.

## 9. Memory invariants

- AI memory remains scoped by user × guild × channel.
- Preserve current retention period.
- Preserve current per-turn/history limits.
- `/forget` continues to distinguish channel history from all-channel deletion.
- Natural-language memory deletion is `WRITE_CONFIRM`, not silent execution.
- Capability telemetry must not copy raw conversation bodies by default.

## 10. Ticket invariants

- Existing ticket records remain compatible.
- Persistent ticket UI remains persistent across restart.
- Existing persistent custom IDs remain compatible.
- Ticket close continues to require the established interaction flow.
- Channel deletion cleanup must continue to reconcile ticket state.
- Do not reset ticket state as part of refactoring.

## 11. Event-view invariants

- `EventView` remains persistent where currently persistent.
- Preserve `ev_join` and `ev_leave` custom IDs.
- Existing event messages must remain operable after code refactors.

## 12. Database invariants

- Production DB path/identity is not renamed or reset.
- No destructive migration without explicit approval.
- Schema changes use migrations.
- Existing public facade behavior remains compatible while repositories/services are introduced.
- Private legacy DB calls may be migrated incrementally, but call-site behavior must be characterized first.
- `database.py` decomposition is a later-stage migration, not a prerequisite for A1/B1.

## 13. Moderation invariants

Natural-language discovery must never reduce existing permission requirements.

For future capability execution:

- `purge`, `kick`, and `ban` are `MODERATION`;
- explicit confirmation is required through the natural-language path;
- existing Discord permission checks remain authoritative;
- model/Jev confidence is never a substitute for authorization.

## 14. Admin invariants

- Admin configuration is `ADMIN`.
- Existing group-level interaction checks remain in force.
- Natural-language discovery may eventually suggest admin capabilities, but cannot silently execute them.
- Server configuration changes require explicit user action.

## 15. Background-task invariants

- Reminder delivery continues to function while reminder creation is migrated.
- Monthly-rule delivery remains operational.
- Memory cleanup retains current retention semantics.
- Background jobs are not automatically exposed as user-selectable capabilities.

## 16. Persistent-data migration rule

Every data-touching capability extraction must answer before merge:

1. What rows/tables does the old path read?
2. What rows/tables does the old path write?
3. Does the new handler preserve transaction/order semantics?
4. Are existing records readable without backfill?
5. Is rollback possible without data conversion?

If these cannot be answered, the change is not ready to merge.

## 17. Capability risk invariants

Initial v4 risk vocabulary:

```text
READ_ONLY
WRITE_CONFIRM
MODERATION
ADMIN
```

Risk is about **execution policy**. Implementation side effects are separately documented.

A read-looking legacy feature such as fortune/profile may perform bookkeeping. Handler extraction must preserve those side effects while still allowing the user-facing policy to be modeled explicitly.

## 18. Telemetry/privacy invariants

Capability-discovery telemetry should default to metadata only:

- router invoked;
- candidate IDs/count;
- confidence;
- selected/dismissed;
- execution success;
- latency;
- relative cost units.

Do not add raw message content or user/guild/channel identifiers merely for discovery analytics without an approved operational need.

## 19. Cost invariants

The future discovery path should prefer:

```text
local gate
→ local shortlist
→ small Jev rerank
→ local registry
→ Discord panel
```

Do not send full conversation history or the entire capability catalog to Jev by default.

Direct slash commands must not incur capability-discovery cost.

## 20. A0 non-goals

A0 must not:

- add a capability runtime;
- change command callbacks;
- change database/schema;
- change AI routing;
- add Jev discovery calls;
- change Discord views;
- change permissions;
- deploy.

A0 is complete when the inventory, architecture baseline, and invariants are reviewable and grounded in the current main branch.
