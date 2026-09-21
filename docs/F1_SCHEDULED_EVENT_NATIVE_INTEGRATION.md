# Release F1 — Native Scheduled Event Integration

## Goal

Make Discord Guild Scheduled Events the canonical event record. Akane becomes a friendly front-end for Discord's native event fields instead of maintaining an independent event model.

## User flow

```text
/event_create OR natural-language event intent
→ choose official event type (Somewhere Else / Voice / Stage)
→ collect official fields
→ preview
→ explicit final confirmation
→ Guild.create_scheduled_event(...)
→ native Discord Scheduled Event becomes source of truth
```

## Fields

- name
- description (optional)
- start date/time (JST input)
- end date/time (required for external; accepted for Voice/Stage)
- external location for Somewhere Else
- Voice/Stage channel for channel-bound events

## Invariants

- Event creation remains WRITE_CONFIRM.
- Candidate selection alone never creates an event.
- Discord Scheduled Event is the canonical record; no independent event DB is introduced.
- Existing ticket/XP/memory/AI/admin behavior is unchanged.
- Poll behavior is unchanged.
- Natural-language discovery remains local-first and cannot authorize creation.
- Bot permission/API failures are visible; there is no silent local-only fallback.

## Command decision

The public slash command is renamed from `/event` to `/event_create` so the command name describes the write action and matches the capability ID. The old bespoke event embed is removed from the creation path.
