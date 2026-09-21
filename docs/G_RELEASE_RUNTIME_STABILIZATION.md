# Release G — Runtime Stabilization

## Goal

Make the v4 general-user runtime and capability catalog stable production concepts instead of exposing historical release-labelled strangler layers.

## Canonical production surfaces

- `cogs.general` — public Discord extension
- `cogs.general_runtime.GeneralCog` — stable general-user runtime class
- `services.capability_catalog.GENERAL_CAPABILITY_SPECS` — canonical 18-capability general catalog
- `services.capability_catalog.DISCOVERY_SPECS` — canonical discovery surface

## Compatibility quarantine

The following remain temporarily because existing characterization tests and inherited implementations still depend on them:

- `cogs.general_commands`
- `cogs.general_v4`
- `cogs.community_v4`
- `DISCOVERY_PILOT_SPECS`
- `DISCOVERY_RELEASE_C_SPECS`
- `DISCOVERY_RELEASE_D_SPECS`
- `DISCOVERY_RELEASE_E_SPECS`

Production entrypoints must not depend on release-labelled catalog names. Historical aliases must preserve behavior until the final deletion pass.

## Invariants

- 18 unique general-user capabilities
- 19 top-level slash commands remain unchanged
- natural-language discovery behavior unchanged
- direct-execution allowlist unchanged
- WRITE_CONFIRM remains fail-closed
- no moderation/admin expansion
- no DB/schema/XP/memory/AI-routing changes
- no ticket or persistent-view changes

## Next cleanup boundary

Physical deletion or rewriting of the large legacy `general_commands.py` is deferred until its remaining progression presentation helpers and command callbacks are extracted behind the stable runtime. Release G establishes the stable seam required to do that without changing production behavior.
