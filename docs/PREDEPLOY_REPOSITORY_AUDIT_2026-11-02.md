# Akane Bot — Predeployment Repository Audit (2026-11-02)

**Scope:** Review GitHub main@39a5c7380282f0c4ce56cd9e28e44d8a133fbb1b and proposed PR #82. Verify the new Light/Standard/Advanced routing, repository integrity, safety and operational deploy conditions.

**Disposition:** Code and automated checks passed on code SHA 288cc090ebe1de5bfbddbab57e54ee85ffef7b82. **Production deployment is NOT approved or performed.** Final-commit CI and Discord human verification remain gates.

## Evidence

- GitHub repository tree fully enumerated: 236 entries (non-truncated). Critical production paths were inspected in configuration, model routing, orchestration, executor, budgets, prompt, cost telemetry, cogs, interaction views, repository/database/migrations, security boundaries, startup, CI and tests. Not every historical document or test was line-reviewed.
- GitHub Actions #898 and #899 successful: Python 3.12/3.13. Verified pytest **396 passed, 1 warning** (3.13); pip check, compileall, pre-dogfood static safety audit and token efficiency R6 acceptance passed.
- Synthetic R6 token footprint benchmark: prompt 1096→654 (−40.3%), history 4332→1861 (−57%), total 5454→2541 (−53.4%). These are synthetic **estimates**, not actual API cost savings.
- Railway read-only check: production service sources branch main from the correct repository; start command python bot.py; single replica; /data mounted to persistent volume; latest deployment marked SUCCESS (2026-10-28). No staged Railway config changes. The protected database content was not opened.

## Routing audit — repaired in PR #82

| Problem | Risk | Repair |
| --- | --- | --- |
| Same model name mistaken for Advanced in every request | HIGH | Classify by route, then effort |
| Cost estimator using unique model identity | HIGH | Route-first estimation, effort fallback |
| Advanced promotion/downgrade checking model identity | HIGH | Check deep-reasoning route |
| Dynamic output cap obscured route identity | MEDIUM | Pass route to output-budget selection |
| Prompt target inferred from model identity | MEDIUM | Explicit effort/character target; default light |
| Luna statistics excluded Advanced and mislabeled Standard | MEDIUM | Shared classifier; separate low/medium/high counters |
| Old test contracts assumed Terra/Sol | MEDIUM | Updated regression tests, added cross-tier checks |

Desired runtime: Light = gpt-6-luna/low; Standard = gpt-6-luna/medium; Advanced = gpt-6-luna/high. Existing 1500/2000/3000 base output caps, Jev classifier, legacy fallback, Advanced promotion threshold, and confirmation boundaries retained. Final output budgets may be lower than base caps.

## Whole-repository waste, duplication and inconsistencies

1. **Compatibility-era duplication (MEDIUM, defer).** Large historical modules, including database.py (~49KB), cogs/general_commands.py (~47KB), cogs/admin_commands.py (~42KB), and cogs/event_handlers.py (~34KB), coexist with repositories/services and stable runtime entrypoints. This is an intentional strangler migration. Deleting without comprehensive call-site compatibility checks is high risk. Plan narrow, independently tested removal PRs after dogfood.
2. **Obsolete dashboard implementation (MEDIUM, defer).** Legacy cogs/admin_commands.py retains a dashboard that counts Luna/Terra/Sol by model identity. Production cogs/admin imports services.gpt6_admin_diagnostics and replaces that dashboard callback, so it is not the active view. Remove the stale body only following compatibility review.
3. **Incomplete cost history (MEDIUM, defer).** CostTelemetry and RoutingTelemetry keep only process-local deques of up to 1000 events. Restarts clear them, so monthly reports are not durable. Reported cost estimates are relative units, not billing currency. Recommend privacy-minimal aggregated persistence and invoice reconciliation in separate design.
4. **Decision-vs-execution mismatch (MEDIUM, defer).** Initial route selection emits telemetry before follow-up downgrade and Advanced gate. The routing-decision dashboard can disagree with actual execution selection; usage records final route/effort. Distinguish provisional/final metrics in another PR.
5. **Specialist-call attribution (LOW/MEDIUM, defer).** Translation, definition, summary explicitly choose models and efforts, while unspecified call-gpt route metadata may be derived from message keywords. This can misattribute usage tiers despite correct execution parameters.
6. **Direct dependency pins but no transitive lock/CVE audit (MEDIUM).** CI checks install, syntax and tests, but no vulnerability/coverage gate. Add curated dependency security and reproducibility workflow independently.
7. **Historical documentation drift (LOW).** Old version/phase files mention Terra and Sol for traceability; updated README/config/runtime policies represent current intended behavior. Annotate archive status, do not mass-rewrite release history.
8. **CI not attached to Railway automatic deployment (HIGH procedural).** Production source configuration reports checkSuites=false and tracks main. A merge can trigger deploy regardless of GitHub CI state. Require green checks and explicit approval before every merge; separately assess merge protection/deploy gating.
9. **Reminder exactly-once limitation (LOW/MEDIUM).** Background reminder is sent before deletion; crash after send before delete may duplicate reminder. This is safer than losing it but not idempotent. Preserve contract for this PR; separate improvement if needed.
10. **Static audit scope (LOW).** The current pre-dogfood static audit tests a few literal invariants; it is not comprehensive SAST or a threat model.

## Safety controls

- Railway bootstrap refuses unexpected persistent volume path or DB path. No PR #82 schema changes.
- Existing DB migrations are additive and transactional; compatibility facade is preserved.
- Reviewed ADMIN UI checks requester identity, administrator privileges at confirmation; ticket operations and moderation have authorization checks. This is not a proof against all security defects.
- No credentials, production database content or live Discord activity were altered.

## Deployment checklist — pending gates

- [x] PR branch only; main and Railway untouched.
- [x] Review critical repo modules and CI failures; repair direct router regressions.
- [x] Python 3.12 and 3.13 tests passed for last reviewed code SHA.
- [x] Confirm Railway main branch and /data persistent mount.
- [ ] Verify GitHub Actions CI PASS for **final PR head SHA**, including this report commit.
- [ ] Human approval for merge and deploy.
- [ ] Railway SUCCESS after approved deploy with preflight, migration, persisted views, four extensions, Discord Gateway READY.
- [ ] Human Discord test: Light/Standard/Advanced; weak deep candidate demotion; short follow-up downgrade; admin AI dashboard; translate/define/summary; cancel/confirmation; ticket persistence.
- [ ] Inspect actual usage, reasoning tokens, incomplete outputs, retry rates, costs and regression versus prior baseline; retain independent database recovery/rollback plan.

**Recommendation:** Router PR may move to human review after final CI. Production go-live remains HOLD until explicit approval and runtime checks. Do not combine unrelated legacy decomposition or database migration with this model change.
