# Release H — Admin / Moderation Capability Integration

## Scope

Release H moves privileged mutations behind Capability Runtime while keeping them out of natural-language discovery.

### MODERATION capabilities

- `/admin kick`
- `/admin ban`
- `/admin purge`

These use `CapabilityRisk.MODERATION`.

### ADMIN write capabilities

- `/admin config_log`
- `/admin config_welcome`
- `/admin config_starboard`
- `/admin config_autochat`
- `/admin config_monthly`
- `/admin setup_ticket`
- `/admin rolepanel`
- `/admin level_reward`
- `/admin level_reward_remove`
- `/admin filter_add`
- `/admin response_add`

These use `CapabilityRisk.ADMIN`.

All privileged mutations are:

- `requires_confirmation=True`
- `discoverable=False`
- reachable only from the existing `/admin` group

## Security contract

Execution path:

`/admin command → group administrator check → requester-only review → administrator permission re-check → confirmed CapabilityRequest → adapter → mutation → audit log`

The review interaction never performs the mutation. Losing administrator permission between slash invocation and final confirmation fails closed. Jev and LLM routing cannot authorize or directly execute these capabilities because they are excluded from `DISCOVERY_SPECS`.

## Preserved invariants

- `/admin` remains server-only and administrator-only.
- Existing command names and primary arguments are preserved.
- Self kick/ban and bot-self kick/ban remain blocked.
- Purge keeps the 300-message maximum and optional member/time filters.
- Discord role hierarchy and bot permissions remain enforced by Discord.
- Ticket persistent UI implementation remains `TicketView`.
- Existing DB schema, XP, memory, AI routing, and general-user capability behavior are unchanged.
- Read-only admin commands such as `status`, `ai_cost`, and `level_reward_list` remain existing admin-group operations; Release H changes only mutation paths.

## Release H completion gate

Release H is complete when:

1. Python 3.12 and 3.13 characterization suites pass.
2. privileged capability sets are disjoint from natural-language discovery.
3. all MODERATION/ADMIN mutations fail closed without confirmation.
4. Railway Production loads `cogs.admin`, syncs the same top-level slash command count, connects to Gateway, and reaches READY.
