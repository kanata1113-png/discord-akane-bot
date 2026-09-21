# Release F2–F10 — Parameterized Capability Execution

## Goal

Complete the natural-language discovery path for general-user capabilities that previously stopped at a Candidate Panel because arguments, external-cost consent, or read-side-effect confirmation were required.

## Interactive capability set

- `message_search` — collect keyword and optional lookback days, then confirm before search
- `rankings` — choose one of `weekly/messages/ai/achievements`, then execute
- `translate` — collect target language and text, then explicitly confirm external AI use
- `define` — collect word/concept and Wiki Mode, then explicitly confirm external AI use
- `summary` — choose recent-message count, then explicitly confirm external AI use
- `fortune` — explicitly confirm before first-read persistence can occur
- `titles` — explicitly confirm before unlock bookkeeping/read presentation runs

## Safety invariants

1. This layer is requester-only.
2. It never changes the `DIRECT_EXECUTION_CAPABILITY_IDS` allowlist.
3. AI-cost capabilities remain selection-only and require a user action after argument collection before the external call.
4. `fortune` and `titles` remain selection-only because their nominal read path can perform persistence/bookkeeping.
5. WRITE_CONFIRM capabilities (`title_set`, `memory_forget`, `remind`, `event_create`, `poll_create`) remain in their existing confirmation flows and are disjoint from the parameterized read layer.
6. Moderation and admin capabilities remain outside this release.
7. Slash command implementations remain the execution adapters, so Candidate Panel and direct slash paths converge on the same production behavior.

## UX contract

`natural language → Candidate Panel → capability selection → argument/scope collection → explicit execute/confirm → existing slash callback → CapabilityDispatcher/handler`

The user should no longer be told to manually re-enter a slash command for any Release F parameterized general-user capability.

## Release gate

- Python 3.12/3.13 CI green
- all historical characterization tests green
- exact parameterized set is frozen by tests
- parameterized and WRITE_CONFIRM sets are disjoint
- discovery policy audit passes
- production boot preserves database/schema/persistent views/slash sync/Gateway connection
