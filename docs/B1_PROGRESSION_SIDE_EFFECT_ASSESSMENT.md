# B1 Progression Pilot — Side-effect Assessment

Baseline: `main@5cf57dc26a8ff1ec848b1d7edfb79f3cf59bb2d0`

## Gate result

The first B1 read-only pilot is successful enough to continue:

- `/level` now uses the capability dispatcher and retained its existing output/error contract.
- `/weekly` now uses the capability dispatcher for its data bundle while Discord presentation remains in the Cog.
- `/rankings` now uses the capability dispatcher for all four existing categories while presentation remains in the Cog.
- No DB schema, XP semantics, AI routing, Jev routing, command names, or permissions were changed.

The next three proposed progression commands are **not equivalent to pure reads** and should not be migrated as one mechanical batch.

## Command classification

| Command | User intent | Legacy mutations / side effects | Recommended capability policy | Migration decision |
|---|---|---|---|---|
| `/profile` | Inspect profile | Calls `evaluate_progress_unlocks` before reads; this may persist newly satisfied achievements/titles | `READ_ONLY` user policy + documented bookkeeping side effect | Safe next extraction after characterization |
| `/achievements` | Inspect achievements | Calls `evaluate_progress_unlocks` before listing; may persist unlocks | `READ_ONLY` user policy + documented bookkeeping side effect | Safe next extraction after characterization |
| `/fortune` | Generate/read daily fortune | First call saves daily fortune, increments fortune count, evaluates unlocks, may emit unlock notifications | Do **not** treat as pure read internally; natural-language execution policy should be reviewed separately | Defer until profile/achievements seam is proven |

## Why user-facing risk and implementation effects are separate

A capability risk level controls what the future natural-language execution path is allowed to do.

It does not claim that the legacy implementation is physically read-only.

For example:

```text
/profile
user intention: inspect
policy: READ_ONLY
implementation bookkeeping:
  evaluate_progress_unlocks()
  → may persist an unlock discovered during the read
```

Changing that bookkeeping merely to make the implementation "pure" would be a behavior change and violates the refactoring invariants.

Therefore B1 should preserve the legacy call order and side effects exactly.

## Required characterization before extraction

### /profile

Preserve this logical order:

```text
evaluate_progress_unlocks
→ get_level_info
→ get_user_stats
→ get_user_achievements
→ get_user_titles
→ get_equipped_title
→ get_user_weekly_xp
→ get_weekly_rank
→ Discord rendering
```

Also preserve:

- optional target member;
- server-only behavior;
- achievement preview ordering;
- title resolution through `Config.TITLES`;
- weekly-rank visibility flag;
- ephemeral response;
- current error response.

### /achievements

Preserve:

```text
evaluate_progress_unlocks
→ get_user_achievements
→ render all Config.ACHIEVEMENTS as locked/unlocked
```

Also preserve optional target member and ephemeral response.

A dedicated guild-presence guard should **not** be added inside the same extraction unless separately approved; that would alter existing behavior.

### /fortune

Before extraction, characterize both branches:

Existing daily fortune:

```text
get_today_fortune
→ render
(no save/increment/unlock evaluation)
```

First fortune of day:

```text
get_today_fortune
→ deterministic JST seed
→ save_today_fortune
→ increment_fortune_count
→ render
→ evaluate_progress_unlocks
→ send unlock notifications
```

The deterministic seed string and thresholds are behavioral contracts and must not be changed during structural migration.

## Next implementation slice

Proceed with `/profile` and `/achievements` together only after adding tests that assert the data-source call order and returned presentation-neutral bundle.

Keep these responsibilities in the Cog for the pilot:

- Discord member display name/avatar;
- Embed construction;
- Config-based labels/descriptions;
- unlock notification presentation.

Defer `/fortune` to the following slice because it combines deterministic domain logic, persistence, progression bookkeeping, deferred Discord response, and optional follow-up notification.
