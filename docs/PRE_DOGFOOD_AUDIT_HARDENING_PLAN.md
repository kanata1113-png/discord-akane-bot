# Pre-Dogfood Audit Hardening Plan

Status: implementation in progress; no freeze.

This batch hardens the production candidate before the one-week public dogfood period. It must not reset, recreate, recompute, or intentionally delete production user state. Protected state includes XP/level, weekly XP, stats, achievements, titles, fortunes, memory, reminders, tickets, guild settings, level rewards, reaction roles, moderation configuration, auto replies, monthly rules, and starboard records.

Planned scope:

1. Make reminder delivery retry-safe so failed Discord sends do not silently lose reminders.
2. Add data/schema protection characterization around additive migrations and production DB identity.
3. Keep migration code as the forward schema authority while retaining legacy init only as a compatibility bootstrap.
4. Make unresolved DatabaseFacade legacy fallbacks auditable without removing compatibility.
5. Replace Intents.all() with the minimum explicit intents required by current features.
6. Apply conservative SQLite durability/concurrency settings without changing database identity or data semantics.
7. Stage static-quality CI with low-noise checks; do not trigger broad refactors.
8. Improve dependency reproducibility and add a current-state README/navigation layer without deleting historical docs.

Explicitly deferred until after dogfood: large event-handler decomposition, broad compatibility-shim deletion, full repository-layer migration, historical-doc deletion, database-file migration/rebuild, and final v4 freeze.