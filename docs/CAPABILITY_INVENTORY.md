# Akane Bot v4 — Capability Inventory

Baseline: `main@7b93abaeb16ef3f57e1cc9808297c8583864b0ac`

Status: **A0 inventory only — no production behavior change**

This inventory describes the user-facing and operator-facing capabilities that exist before the v4 capability runtime is introduced. It is the migration map, not yet an executable registry.

## Risk vocabulary

- `READ_ONLY`: reads or renders state without intentionally mutating shared configuration. Existing counters/unlock evaluation may still occur as part of legacy behavior.
- `WRITE_CONFIRM`: creates, deletes, or changes user/community-visible state and should require confirmation when reached through future natural-language discovery.
- `MODERATION`: privileged member/message moderation.
- `ADMIN`: server configuration or privileged operational action.
- `AI_GENERATION`: invokes an AI-backed content operation; execution is non-destructive but has external cost.

## General slash capabilities

| Capability ID | Slash command | User-facing purpose | Category | Current implementation | Main dependencies | Side effects | Risk | Persistent UI | Existing coverage / migration target |
|---|---|---|---|---|---|---|---|---|---|
| translate | `/translate` | AI translation | AI tools | `GeneralCog.translate` | `AiManager` / AI platform | AI request | AI_GENERATION | No | command characterization; later AI capability handler |
| define | `/define` | AI dictionary / optional wiki mode | AI tools | `GeneralCog.define` | AI manager | AI request | AI_GENERATION | No | command characterization; later AI capability handler |
| summary | `/summary` | Summarize caller's recent messages | AI tools | `GeneralCog.summary` | Discord history + AI manager | Reads channel history; AI request | AI_GENERATION | No | command characterization; later AI capability handler |
| event_create | `/event` | Create event panel | Community | `GeneralCog.event` | Discord message + `EventView` | Creates message/view | WRITE_CONFIRM | `EventView` custom IDs `ev_join`, `ev_leave` | view characterization; later community handler |
| poll_create | `/poll` | Create poll | Community | `GeneralCog.poll` | Discord reactions/messages | Creates poll message/reactions | WRITE_CONFIRM | No | command characterization; later community handler |
| message_search | `/search` | Search server messages | Community | `GeneralCog.search` | Discord channel history | Reads message history | READ_ONLY | No | command characterization; later search handler |
| level | `/level` | Show caller XP/level | Progression | `GeneralCog.level` | `bot.db.get_level_info` | Read | READ_ONLY | No | **B1 pilot** |
| leaderboard | `/leaderboard` | Global level/XP TOP30 | Progression | `GeneralCog.leaderboard` | `bot.db.get_leaderboard` | Read | READ_ONLY | No | progression characterization; later handler |
| remind | `/remind` | Create reminder | Utility | `GeneralCog.remind` | DB reminder + background loop | Persists reminder; later sends message | WRITE_CONFIRM | No | **B1 pilot** |
| memory_status | `/memory` | Show stored AI-memory status | AI memory | `GeneralCog.memory` | conversation DB/service | Read | READ_ONLY | No | memory tests; later memory handler |
| memory_forget | `/forget` | Delete caller AI conversation history | AI memory | `GeneralCog.forget` | conversation DB/service | Deletes conversation history | WRITE_CONFIRM | No | memory tests; later memory handler |
| profile | `/profile` | Show profile/progression | Progression | `GeneralCog.profile` | level, stats, achievements, titles, weekly ranking | Legacy unlock evaluation may write unlocks | READ_ONLY* | No | **B1 pilot**; preserve legacy unlock semantics |
| fortune | `/fortune` | Daily fortune | Progression/fun | `GeneralCog.fortune` | fortune DB + progress unlocks | First call persists daily fortune/count/unlocks | READ_ONLY* | No | **B1 pilot**; preserve deterministic semantics |
| achievements | `/achievements` | Show achievements | Progression | `GeneralCog.achievements` | progress DB/config | Legacy unlock evaluation may write unlocks | READ_ONLY* | No | **B1 pilot** |
| titles | `/titles` | Show earned titles | Progression | `GeneralCog.titles` | progress DB/config | Legacy unlock evaluation may write unlocks | READ_ONLY* | No | later progression handler |
| title_set | `/title_set` | Equip profile title | Progression | `GeneralCog.title_set` | title DB/config | Changes equipped title | WRITE_CONFIRM | No | later progression handler |
| weekly | `/weekly` | Weekly XP ranking | Progression | `GeneralCog.weekly` | weekly XP/ranking DB | Read | READ_ONLY | No | **B1 pilot** |
| rankings | `/rankings` | Server rankings by weekly XP/messages/AI/achievements | Progression | `GeneralCog.rankings` | ranking DB methods | Read | READ_ONLY | No | **B1 pilot** |

`READ_ONLY*` means the user-visible operation is read-like, but the legacy implementation performs bookkeeping/unlock persistence. v4 adapters must preserve that behavior rather than silently reclassifying implementation semantics.

## Admin group capabilities

All commands below are exposed beneath the `/admin` app-command group and pass through `AdminCommands.interaction_check`. Natural-language discovery must never bypass the existing authorization boundary.

| Capability ID | Slash command | Purpose | Current implementation | Main dependencies | Side effects | Risk | Migration target |
|---|---|---|---|---|---|---|---|
| admin_status | `/admin status` | Inspect bot/server configuration | `AdminCommands.status` | config + DB | Read | ADMIN | admin diagnostics |
| admin_ai_cost | `/admin ai_cost` | Inspect AI cost/model telemetry | `AdminCommands.ai_cost` | cost telemetry | Read | ADMIN | admin diagnostics |
| config_log | `/admin config_log` | Configure audit-log channel | `AdminCommands.config_log` | guild config DB | Writes config | ADMIN | admin config handler |
| config_welcome | `/admin config_welcome` | Configure welcome channel | `AdminCommands.config_welcome` | guild config DB | Writes config | ADMIN | admin config handler |
| config_starboard | `/admin config_starboard` | Configure starboard channel | `AdminCommands.config_starboard` | guild config DB | Writes config | ADMIN | admin config handler |
| config_autochat | `/admin config_autochat` | Configure resident AI chat channel | `AdminCommands.config_autochat` | guild config DB | Writes config | ADMIN | admin config handler |
| config_monthly | `/admin config_monthly` | Configure monthly rules notification | `AdminCommands.config_monthly` | direct legacy DB access | Writes monthly rule config | ADMIN | admin config + repository migration |
| ticket_setup | `/admin setup_ticket` | Install ticket panel | `AdminCommands.setup_ticket` | `TicketView` | Creates persistent panel message | ADMIN | support/admin handler |
| rolepanel | `/admin rolepanel` | Bind reaction to role | `AdminCommands.rolepanel` | direct legacy DB + Discord message | Writes role-panel rule | ADMIN | admin role handler |
| level_reward_set | `/admin level_reward` | Configure level role reward | `AdminCommands.level_reward` | direct legacy DB | Writes reward rule | ADMIN | progression admin handler |
| level_reward_remove | `/admin level_reward_remove` | Remove level reward | `AdminCommands.level_reward_remove` | direct legacy DB | Deletes reward rule | ADMIN | progression admin handler |
| level_reward_list | `/admin level_reward_list` | List level rewards | `AdminCommands.level_reward_list` | direct legacy DB | Read | ADMIN | progression admin handler |
| filter_add | `/admin filter_add` | Add NG word | `AdminCommands.filter_add` | direct legacy DB | Writes moderation rule | ADMIN | moderation config handler |
| response_add | `/admin response_add` | Add automatic response | `AdminCommands.response_add` | direct legacy DB | Writes response rule | ADMIN | community automation handler |
| kick_member | `/admin kick` | Kick member | `AdminCommands.kick` | Discord moderation API | Removes member | MODERATION | moderation handler |
| ban_member | `/admin ban` | Ban member | `AdminCommands.ban` | Discord moderation API | Bans member | MODERATION | moderation handler |
| purge_messages | `/admin purge` | Bulk-delete messages | `AdminCommands.purge` | Discord message API | Deletes messages | MODERATION | moderation handler |

## Event-driven / automatic capabilities

These are capabilities of the bot even though they are not slash commands. They are **not initial natural-language discovery targets** unless a later phase explicitly promotes them.

| Capability | Trigger | Current owner | Main behavior / dependency | Migration note |
|---|---|---|---|---|
| spam_protection | message | `EventsCog.on_message` / `handle_spam` | thresholds, timeout escalation | Keep event-driven; separate moderation service later |
| ng_word_filter | message | `EventsCog.on_message` | legacy DB word rules | Keep event-driven |
| custom_auto_response | message | `EventsCog.on_message` | DB trigger/response rules | Keep event-driven |
| resident_ai_chat | configured-channel message | `EventsCog.on_message` | memory + AI control plane + daily limit | Preserve current AI route and memory behavior |
| xp_award | eligible message | `EventsCog.on_message` | XP service/facade + cooldown | Preserve global XP semantics |
| weekly_xp_award | eligible message | `EventsCog.on_message` | weekly XP DB | Preserve guild/JST semantics |
| progress_unlock | progression events | `EventsCog`, commands, ticket view | achievements/titles | Duplicate notification paths are existing debt |
| level_role_reward | level-up | `EventsCog.on_message` | DB reward rules + Discord roles | Later progression service |
| reaction_role | reaction add/remove | `EventsCog` | role-panel DB + Discord roles | Later community/admin boundary |
| reaction_translate | reaction add | `EventsCog.on_raw_reaction_add` | flag map + AI | Later AI utility boundary |
| starboard | reaction add | `EventsCog.on_raw_reaction_add` | guild config + DB dedupe | Later community service |
| audit_message_delete | message delete | `EventsCog.on_message_delete` | configured log channel | Later moderation/audit service |
| audit_voice | voice state | `EventsCog.on_voice_state_update` | configured log channel | Later audit service |
| welcome | member join | `EventsCog.on_member_join` | configured welcome channel | Later community service |
| ticket_channel_cleanup | channel delete | `EventsCog.on_guild_channel_delete` | ticket DB | Keep support invariant |
| reminder_delivery | background loop | `BackgroundTasksCog.loop_reminders` | maintenance repository/service | Existing claim-before-send behavior is debt |
| monthly_rule_delivery | background loop | `BackgroundTasksCog.loop_monthly` | monthly rules | Later community/admin service |
| memory_cleanup | background loop | `BackgroundTasksCog.loop_memory_cleanup` | memory service | Preserve retention semantics |

## Persistent Discord UI

| UI | Owner | Persistence contract | Notes |
|---|---|---|---|
| Event join/leave | `views/event_view.py` | `timeout=None`; `ev_join`, `ev_leave` | Existing event messages depend on custom-ID compatibility |
| Ticket category panel | `views/ticket_view.py` | persistent category select | Creates ticket channels and DB records |
| Ticket close | `views/ticket_view.py` | persistent close button | Confirmation view itself is transient |
| Ticket transcript | `views/ticket_view.py` | generated on close flow | Coupled to ticket lifecycle |

## A0 findings

1. There are **18 top-level general slash commands** plus **17 admin subcommands**. Discord sync may report the admin group as one top-level command, so top-level sync counts must not be confused with capability count.
2. The repository already contains a partial Service/Repository migration. `DatabaseFacade` routes selected stable APIs through `ServiceRegistry`, while many admin/event paths still use legacy private DB helpers.
3. Progression is the best B1 pilot because it contains multiple read-oriented capabilities with clear inputs and existing characterization coverage.
4. `remind` is a useful first `WRITE_CONFIRM` pilot, but should not be the first natural-language execution target.
5. Event-driven automation must be represented in the architecture map even though it should not initially appear in the natural-language capability registry.
6. The v4 registry should initially describe slash-addressable capabilities; automatic/event capabilities should remain a separate registry namespace or inventory section until a concrete need exists.
7. `profile`, `fortune`, and `achievements` demonstrate why risk metadata and implementation side effects must be distinct: they look read-only to users but can persist progression bookkeeping.
