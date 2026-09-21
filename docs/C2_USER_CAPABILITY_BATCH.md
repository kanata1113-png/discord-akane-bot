# Release C2 — User Capability Strangler Batch

## Scope

This batch migrates five existing general commands behind CapabilityDispatcher
without changing their slash-command surface:

- `/titles`
- `/title_set`
- `/memory`
- `/forget`
- `/remind`

The migration introduces a strangler subclass rather than rewriting the legacy
GeneralCog. Unmigrated commands remain inherited from the production class.

## Architecture

```text
cogs/general.py
→ cogs/general_v4.GeneralCog
   ├─ migrated overrides
   │  → User CapabilityDispatcher
   │  → capability handler
   │  → existing DB facade/data source
   └─ all other commands
      → inherited LegacyGeneralCog behavior
```

## Risk boundary

READ_ONLY:

- `titles` — retains legacy unlock evaluation before reading titles
- `memory_status`

WRITE_CONFIRM:

- `title_set`
- `memory_forget`
- `remind`

CapabilityDispatcher rejects every WRITE_CONFIRM request unless
`confirmed=True`. Existing direct slash invocations pass `confirmed=True`
because the user explicitly invoked the command. Future natural-language paths
must satisfy their own explicit confirmation interaction before dispatch.

## Preserved behavior

- slash names and argument shapes are unchanged;
- reminder validation remains 1–10080 minutes and <=500 characters;
- `/forget` retains channel-only vs all-channel scope;
- `/titles` retains unlock bookkeeping before rendering;
- `/title_set` still rejects unknown or unowned titles;
- memory scope remains user × guild × channel;
- DB schema and persistence format are unchanged;
- AI routing is unchanged;
- moderation/admin boundaries are unchanged.

## Verification gate

- inherited application-command surface is identical to the legacy cog;
- only the five migrated callbacks are overridden;
- write handlers fail closed without confirmation;
- existing regression suite must pass on Python 3.12 and 3.13.
