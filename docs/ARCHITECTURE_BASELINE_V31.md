# Akane Bot — Architecture Baseline v3.1

Baseline commit: `7b93abaeb16ef3f57e1cc9808297c8583864b0ac`

Purpose: freeze the pre-v4 architecture in documentation so later refactors can be checked against an explicit baseline.

## Runtime composition

```text
Discord Gateway / Interactions
        │
        ├─ app.py / AkaneBot
        │    ├─ DatabaseManager (legacy)
        │    ├─ RepositoryRegistry
        │    ├─ ServiceRegistry
        │    ├─ DatabaseFacade
        │    └─ AiManager
        │
        ├─ cogs/general_commands.py
        ├─ cogs/admin_commands.py
        ├─ cogs/event_handlers.py
        ├─ cogs/background.py
        │
        ├─ views/event_view.py
        └─ views/ticket_view.py
```

The codebase is already in a transitional architecture: legacy DB/business logic remains active while selected domains have Service and Repository seams.

## AI request path

```text
Discord message / AI utility
        ↓
AiManager compatibility facade
        ↓
AIControlPlane / AIOrchestrator
        ├─ ContextBuilder
        ├─ IntentController / gates
        ├─ RoutingPolicy
        │    ├─ legacy selection
        │    ├─ JevModelRouter / providers
        │    ├─ continuity/fallback
        │    ├─ FollowupDowngrade
        │    └─ SolPromotionGate
        ├─ DetailIntent
        ├─ OutputBudget / budget controllers
        ├─ HistoryOptimizer
        ├─ PromptBuilder
        └─ AIExecutor
             ↓
          OpenAI Responses API
```

Observability is split across routing/control-plane metrics and cost telemetry. Evaluation and benchmark utilities are repository-local and do not belong to the Discord execution surface.

## Model-routing baseline

Production intent is:

```text
normal-chat                         → FAST_MODEL / Luna
reasoning / regulation / long text → CHAT_MODEL / Terra
deep-reasoning                     → REASONING_MODEL / Sol
```

Sol remains subject to promotion policy. Follow-up downgrade and continuity behavior are part of the baseline and must not be altered incidentally by capability work.

## Data architecture

```text
Discord-facing code
       ↓
 DatabaseFacade
   ┌───┴─────────────────────┐
   ↓                         ↓
ServiceRegistry          legacy DatabaseManager
   ↓                         ↓
RepositoryRegistry       legacy public/private DB methods
   ↓                         ↓
             SQLite
```

### Existing repositories

- `UserRepository`
- `GuildRepository`
- `MemoryRepository`
- `RankingRepository`
- `TicketRepository`
- `MaintenanceRepository`

### Existing services

- `XPService`
- `MemoryService`
- `TicketService`
- `ProgressService`
- `MaintenanceService`

`ProgressService` still delegates to the legacy database for several progression operations. This is an intentional migration seam, not evidence that the Service/Repository migration is complete.

## Command surface

### General

`GeneralCog` owns 18 slash commands spanning unrelated domains:

- AI tools: translate, define, summary
- community: event, poll, search, remind
- AI memory: memory, forget
- progression/profile: level, leaderboard, profile, fortune, achievements, titles, title_set, weekly, rankings

### Admin

`AdminCommands` owns 17 subcommands spanning:

- diagnostics: status, ai_cost
- guild configuration: log, welcome, starboard, autochat, monthly
- support: ticket setup
- roles/progression: role panel, level rewards
- automation/moderation config: filters, custom responses
- destructive moderation: kick, ban, purge

The group-level `interaction_check` is a security boundary that v4 must preserve.

## Event surface

`EventsCog` currently combines:

- spam detection/enforcement;
- NG-word filtering;
- custom responses;
- resident AI chat;
- XP and weekly XP;
- progress unlocks and level-role rewards;
- reaction roles;
- reaction translation;
- starboard;
- message-delete logging;
- voice logging;
- welcome messages;
- ticket cleanup.

This is a major responsibility concentration, but A0 does not change it.

## Background surface

`BackgroundTasksCog` owns:

- reminder delivery;
- monthly-rule delivery;
- conversation-memory cleanup.

These jobs are runtime capabilities but are not candidate user actions.

## Persistent UI

`EventView` and ticket views carry compatibility contracts across restarts. Their custom IDs and persistence semantics must survive refactors.

Ticket UI is itself a large domain component: category selection, channel creation, lifecycle, close confirmation, transcript creation, and progression notifications are coupled in `views/ticket_view.py`.

## Structural hotspots

At the A0 baseline, the largest responsibility concentrations include approximately:

```text
database.py             ~49 KB
general_commands.py     ~49 KB
admin_commands.py       ~38 KB
event_handlers.py       ~32 KB
ticket_view.py          ~30 KB
routing_policy.py       ~14 KB
config.py               ~11 KB
```

Size alone is not a defect. The relevant issue is responsibility concentration and mixed migration generations.

## v4 capability seam

The intended seam is additive:

```text
Existing slash command ─────┐
                            ↓
                    Capability Handler
                            ↑
Future candidate panel ─────┘
```

A0 intentionally does **not** create this runtime seam. A1 will introduce the smallest useful capability core after this baseline is reviewed.

## Migration boundaries

### Good early extraction targets
- progression read paths;
- ranking read paths;
- profile/achievement rendering;
- reminder creation after read-only pilot validation.

### Defer until later
- `database.py` decomposition;
- ticket lifecycle rewrite;
- event-handler decomposition;
- moderation/admin natural-language execution;
- AI routing redesign.

## Known architectural debt relevant to v4

- direct calls to legacy DB private helpers remain in admin/event code;
- command modules span multiple domains;
- ticket view contains business logic and presentation logic;
- progress unlock notifications have more than one call path;
- reminder delivery currently has claim/delivery coupling that deserves separate hardening;
- Service/Repository migration is partial;
- AI routing has several cooperating modules whose authority must remain documented during refactors.

These are migration inputs, not A0 implementation tasks.

## Baseline conclusion

Akane v3.1 is not a single monolith. It is a **hybrid architecture**: mature AI-control-plane modules and emerging Service/Repository boundaries coexist with older command/event/database concentrations.

v4 should therefore use a strangler migration rather than replace the existing architecture wholesale.
