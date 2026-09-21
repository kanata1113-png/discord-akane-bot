# Akane Bot v4.0.0 — Production Baseline

Status: **Release I / Production Completion candidate**

Baseline parent: `main@c254c64c7c861a35457115f07df77db3b8de935a`

## Release definition

v4.0.0 freezes the Capability Runtime migration as a production contract. Release I is a stabilization and verification release: it does not intentionally add user-facing features, change database schema, alter AI routing, or broaden natural-language authorization.

### Capability inventory

- 18 general-user slash capabilities
- 17 `/admin` subcommands
- 35 slash-addressable capabilities in the inventory
- 32 modeled Capability Runtime entries:
  - 18 general-user
  - 11 ADMIN mutations
  - 3 MODERATION mutations
- 3 authorized read-only admin diagnostics remain slash-only:
  - `/admin status`
  - `/admin ai_cost`
  - `/admin level_reward_list`
- Discord sync remains 19 top-level commands because `/admin` is one top-level command group.

## Frozen execution boundaries

### Direct natural-language execution after explicit requester selection

Exactly six READ_ONLY capabilities:

- `level`
- `leaderboard`
- `weekly`
- `profile`
- `achievements`
- `memory_status`

No external-cost, WRITE_CONFIRM, MODERATION, or ADMIN capability is direct-executable.

### Selection / parameter / confirmation path

The other 12 general-user capabilities remain selection-only and use their established parameter or confirmation flows. WRITE_CONFIRM remains fail-closed.

### Privileged operations

All 14 privileged mutations are hidden from natural-language discovery.

`/admin → administrator gate → requester-only review → administrator re-check → confirmed CapabilityRequest → mutation → audit`

Jev/LLM may not authorize privileged execution.

## Frozen runtime surfaces

- `cogs.general.GeneralCog` resolves to `cogs.general_runtime.GeneralCog`
- `cogs.admin.AdminCommands` resolves to `cogs.admin_runtime.AdminCommands`
- `services.capability_catalog.GENERAL_CAPABILITY_SPECS` is the canonical 18-capability general catalog
- `services.capability_catalog.DISCOVERY_SPECS` is the canonical general discovery surface
- `services.production_baseline.validate_v4_production_baseline()` is the machine-readable release drift gate

Historical release-labelled modules/aliases may remain as compatibility implementation details. They are not production entrypoints and are not deleted in Release I.

## Data and behavior invariants

Release I preserves:

- production DB identity `/data/akane_v26.db`
- schema migration discipline and schema version compatibility
- global XP identity, 10 XP / 60-second cooldown
- guild-scoped weekly XP with JST semantics
- deterministic fortune behavior and bookkeeping
- user × guild × channel memory scope and 30-day retention
- ticket records, persistent ticket UI and cleanup
- persistent EventView IDs `ev_join` / `ev_leave`
- scheduled-event integration behavior established before Release I
- reminder/monthly/memory-cleanup background jobs
- Luna/Terra/Sol routing roles, Jev routing, response guards, context optimization, and metadata-only cost telemetry

## Release gate

A v4.0.0 release candidate is technically acceptable only when all of the following pass:

1. Python 3.12 compile + full pytest suite.
2. Python 3.13 compile + full pytest suite.
3. Release I production-baseline drift gate.
4. Existing Release C–H regression gates.
5. Railway Production deployment reaches SUCCESS.
6. Runtime preflight passes with `/data` volume.
7. DB initializes without destructive migration.
8. Persistent views load.
9. `cogs.admin`, `cogs.general`, `cogs.events`, `cogs.background` load.
10. Discord slash sync remains 19 top-level commands.
11. Gateway connects and bot reaches READY.
12. Human Verification is performed before the release is declared accepted.

## Human Verification

Release I deliberately separates technical completion from human acceptance. The final Discord smoke should cover representative paths without destructive experimentation:

- one READ_ONLY direct-execution discovery flow
- one parameterized READ_ONLY flow
- one WRITE_CONFIRM cancel flow and one confirmed benign write
- one AI-generation parameter flow
- event creation / native scheduled-event visibility
- ticket persistent UI after restart
- one ADMIN configuration confirmation/cancel check
- MODERATION confirmation UI without confirming a destructive action
- ordinary AI chat fallback for a non-capability message

Only after these checks should v4.0.0 be marked **Human Accepted / Production Baseline Frozen**.
