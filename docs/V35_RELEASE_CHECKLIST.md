# v35 Railway release checklist

This checklist is intentionally operational only. It does not change Discord-visible behavior.

## Release gate

Before deploying v35 to production:

- [ ] GitHub Actions passes `compileall` and the full pytest suite on Python 3.12 and 3.13.
- [ ] Railway service start command remains `python bot.py` (or its existing equivalent that starts `bot.py`).
- [ ] `DISCORD_TOKEN` and `OPENAI_API_KEY` remain configured in Railway service variables.
- [ ] The persistent Railway Volume is attached to the bot service at `/data`.
- [ ] Railway exposes `RAILWAY_VOLUME_MOUNT_PATH=/data` at runtime.
- [ ] `/data/akane_v26.db` is backed up before the first v35 production deployment.
- [ ] Do not rename, recreate, truncate, or replace `akane_v26.db` as part of the v35 release.

The application now fails startup on Railway if the `/data` volume is absent or mounted somewhere else. Local development still uses the existing `akane_v26.db` fallback.

## Expected startup log sequence

After deployment, confirm the logs contain all of the following without an exception between them:

1. `Runtime preflight passed.`
2. `Database initialized: /data/akane_v26.db`
3. `Database schema version: 1`
4. `Persistent views loaded.`
5. `Extension loaded: cogs.admin`
6. `Extension loaded: cogs.general`
7. `Extension loaded: cogs.events`
8. `Extension loaded: cogs.background`
9. `Slash commands synced:`
10. `setup_hook completed.`
11. `Akane Bot v34 READY`

The v34 log label is retained in v35 because changing user/runtime-facing version strings was outside the refactor scope.

## Production smoke test

After the bot becomes ready, verify a small representative set without mutating existing server configuration:

- [ ] `/level` returns the existing profile/XP information.
- [ ] `/profile` returns the existing profile shape and equipped title behavior.
- [ ] `/fortune` returns today's fortune normally.
- [ ] `/weekly` or `/rankings` returns without a DB error.
- [ ] `/memory` returns without a DB error.
- [ ] A normal message still awards XP subject to the existing 60-second cooldown.
- [ ] AI mention/auto-chat still routes and replies normally.
- [ ] Existing persistent Ticket controls still respond after restart.
- [ ] Background task startup appears once; no duplicate reminder/monthly/memory-cleanup loop is observed.

## Database verification

The v35 baseline must keep the same production database path:

```text
/data/akane_v26.db
```

Migration version 1 is a baseline marker for the already-existing v34 schema. It must not delete or recreate user tables. Re-running migrations is expected to be a no-op.

For a backup, use the Railway Volume file tooling or another existing operational backup method. The backup must be taken from the persistent Volume; do not copy a local fallback database and treat it as production.

## Rollback

If v35 fails after deployment:

1. Stop/redeploy the application code to the last known-good baseline; do not delete the Volume.
2. Prefer the Phase 6 baseline commit as the first code rollback target:

```text
ca532b280595da62f644d069df34c214682907a1
```

3. Keep `/data/akane_v26.db` in place. Phase 7 adds no schema migration.
4. Restore the DB backup only if there is evidence that the database itself was corrupted or unintentionally modified; do not restore merely because application startup failed.
5. Re-check Volume mount path, Railway variables, startup logs, and Discord login before attempting another deployment.

## v35 invariants

Do not treat the following as cleanup opportunities during release:

- Production DB filename remains `akane_v26.db`.
- Normal XP remains global by `user_id`; weekly XP remains guild-scoped.
- XP remains 10 per eligible message with a 60-second in-memory cooldown.
- Fortune seed/behavior, AI routing, command names/descriptions, messages, and Persistent View IDs remain unchanged.
- Spam and XP cooldown state remain in memory and reset on restart.
