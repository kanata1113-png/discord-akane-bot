# 表自派 茜 / Akane Bot

Discord community bot for conversation, progression, search, translation, reminders, scheduled events, moderation/admin workflows, native tickets, and AI-assisted features.

## Current status

- Production branch: `main`
- Production host: Railway
- Production database: `/data/akane_v26.db`
- Current phase: post-implementation dogfood / debugging candidate
- Final v4 freeze: **deferred until after the public dogfood period**

The repository contains historical release and phase documents for traceability. They are not all current contracts. Start with the documents listed below.

## Current architecture

```text
Discord events / slash commands / views
        ↓
Cog and UI adapters
        ↓
Capability Runtime / domain services
        ↓
Repositories / compatibility facade
        ↓
SQLite (/data/akane_v26.db in Railway Production)
```

Production entrypoint: `bot.py` → `app.AkaneBot`.

Current OpenAI routing target:

- Light: `gpt-6-luna` / `low`
- Standard: `gpt-6-luna` / `high`
- Advanced: `gpt-6-sol` / `medium`
- OpenAI execution boundary: Responses API
- Jev remains the routing/preprocessing layer and never authorizes privileged actions.

Stable extension entrypoints:

- `cogs.admin`
- `cogs.general`
- `cogs.events`
- `cogs.background`

## Data-safety invariants

Production state must not be reset, recreated, or recomputed as part of routine refactoring. Protected state includes, at minimum:

- XP and level
- weekly XP
- user stats, achievements, titles, fortunes
- conversation memory
- reminders
- tickets and ticket audit/member data
- guild settings and level rewards
- reaction roles
- moderation/filter configuration and auto replies
- monthly rules
- starboard records

Railway startup fails closed if `/data` is not mounted or the configured database path drifts away from `/data/akane_v26.db`.

Forward schema changes belong in `db_migrations.py` and should remain additive unless a separately reviewed migration explicitly requires otherwise. `DatabaseManager.init()` remains as a compatibility bootstrap while the repository/service migration is unfinished.

## Important current documents

- `docs/REFACTORING_INVARIANTS.md` — architecture and safety invariants
- `docs/PRE_DOGFOOD_AUDIT_HARDENING_PLAN.md` — current audit-hardening batch
- `docs/V4_PRODUCTION_BASELINE.md` — Release I baseline candidate; historical relative to newer dogfood additions and **not the final freeze**
- `docs/RELEASE_I_FINAL_VERIFICATION.md` — Release I verification record

Other phase/release documents are retained as development history unless explicitly promoted to a current contract.

## Development gate

CI currently runs on Python 3.12 and 3.13 and performs dependency validation, compilation, repository safety checks, and the pytest suite.

Normal development flow:

```text
feature branch
→ tests / CI
→ review
→ merge to main
→ Railway auto-deploy
→ runtime verification
→ Human Verification / dogfood
```

Do not manually rebuild or replace the production SQLite database during routine feature work.
