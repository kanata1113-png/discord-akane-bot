# v4 UX Completion & Akane Native Ticket

Status target: `PUBLIC_DOGFOOD_READY`

This batch intentionally does **not** freeze the v4.0.0 production baseline. After Production deployment and Human Verification, the server will run an approximately one-week public dogfood period. Baseline freeze is deferred until dogfood findings are repaired and re-verified.

## 1. Discovery UX

- Candidate Panel copy is human-facing Akane dialogue with moderate emoji.
- Internal labels such as READ_ONLY / WRITE_CONFIRM are not shown to ordinary users.
- Selecting a write or parameterized candidate starts its real input flow immediately; the old duplicate second capability button is removed.
- Final confirmation remains mandatory for mutations and external-AI execution where already required.
- Admin / moderation authorization boundaries are unchanged.

## 2. Message Search UX

Search results are presented as compact cards:

- author
- query-relevant local snippet
- relative time
- original-message link

Markdown/noise is normalized locally. No GPT call is made per result. More than 20 matches may include a text export while the Discord preview stays compact.

## 3. Scheduled Event Wizard

Discord Scheduled Events remain the canonical event source.

Natural-language event creation now uses:

1. Voice
2. Stage
3. External / Other

Voice and Stage use a Discord Channel Select filtered to the matching channel type. Users never need to remember channel IDs.

Start date and start time are separate fields. Time input accepts friendly forms such as `18:00`, `18：00`, and `1800`. Same-day end time may be entered as `22:00`; cross-day end accepts a full date/time.

The final preview/confirmation remains mandatory before creation.

## 4. Akane Native Ticket

The external Ticket Tool remains installed during this release. Removal is a later, separately approved migration task.

### Creation

- public persistent Ticket panel remains supported
- natural language such as `管理人に問い合わせたい` routes locally to native Ticket creation
- content is collected in a Discord modal
- final confirmation is required before a channel is created
- channels use sequential names such as `ticket-0001`
- default category is `🎫｜お問い合わせ`
- duplicate open Ticket protection remains

### Visibility

Ticket channel access is limited to:

- requester
- Discord Administrators
- Akane
- configured Ticket Staff role
- explicitly added Ticket members

The Staff role is configurable from the persistent Ticket panel by an Administrator.

### Operations

Persistent Ticket controls include:

- Close
- Claim
- Reopen
- Manage

Staff management includes:

- Rename
- Add member
- Remove member
- permanent Delete with a second confirmation

Close no longer immediately deletes the channel. It marks the Ticket closed, makes the requester read-only, preserves transcript/history, and allows Staff to reopen it. Permanent deletion is a distinct Staff-only destructive operation.

### Persistence / Audit

Schema migration v2 is additive and adds:

- ticket number / subject / assignee metadata
- guild Ticket settings
- per-guild sequential counters
- extra Ticket members
- Ticket audit records

The historical `ticket_close_button` custom ID is preserved for existing persistent messages.

## 5. Safety invariants

- Jev/LLM never authorizes Ticket/Admin/Moderation actions.
- Ticket natural-language intent is locally gated and bypasses Jev authorization.
- Candidate selection alone does not perform mutations.
- final mutation confirmation remains requester-only.
- Staff-only operations check Administrator or configured Staff role at execution time.
- Ticket Tool is not kicked, removed, or reconfigured in this batch.
- existing 18 general capability catalog and 19 top-level slash-command target remain unchanged.
- database migration is additive; `/data/akane_v26.db` remains the canonical database.

## 6. Release gate

Before `PUBLIC_DOGFOOD_READY`:

1. compileall on Python 3.12 / 3.13
2. full pytest characterization suite
3. existing C–I regression gates
4. migration v1 → v2 / unversioned adoption tests
5. Ticket persistence and native-operation tests
6. merge to main only after green CI
7. Railway Production deployment SUCCESS
8. runtime preflight and schema v2 confirmation
9. 19 top-level slash commands synced
10. Gateway READY
11. Human Verification

After these pass, status is `PUBLIC_DOGFOOD_READY`, **not Frozen**.

## 7. Post-deployment

Run approximately one week of real-server dogfood. Collect interaction failures, permission edge cases, UX friction, and Ticket/Event/Search feedback. Repair and re-run the full gate. Only after separate Human Acceptance should v4.0.0 baseline freeze be considered.
