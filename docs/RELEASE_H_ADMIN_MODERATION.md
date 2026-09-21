# Release H — Admin / Moderation Capability Integration

## Scope

Release H migrates the destructive moderation commands into Capability Runtime without exposing them to natural-language discovery.

Migrated commands:

- `/admin kick`
- `/admin ban`
- `/admin purge`

## Security contract

Each migrated capability is:

- `CapabilityRisk.MODERATION`
- `requires_confirmation=True`
- `discoverable=False`
- reachable only from the existing `/admin` command group

Execution path:

`/admin command → existing group administrator check → requester-only review → administrator permission re-check → confirmed CapabilityRequest → adapter → Discord mutation → audit log`

The selection/review interaction never performs the mutation. Losing administrator permission between the slash invocation and final confirmation fails closed.

## Preserved invariants

- `/admin` remains server-only and administrator-only.
- Command names and primary arguments remain unchanged.
- Self kick/ban and bot-self kick/ban remain blocked.
- Purge keeps the 300-message maximum and optional member/time filters.
- Discord role hierarchy and bot permissions remain enforced by Discord.
- Moderation capabilities are not added to `DISCOVERY_SPECS`.
- Jev/LLM cannot authorize or directly execute moderation.
- Existing admin configuration, ticket, reaction-role, filter, auto-response, level-reward, DB, XP, memory, and AI routing behavior is untouched in this release.

## Follow-up

Remaining `/admin` configuration writes are still legacy admin operations. They can be modeled as `ADMIN` capabilities in a later hardening slice after the destructive moderation boundary is verified in Production.
