# Release E — Community Capability Waterfall Gate

## Scope

Release E completes Capability Runtime representation for the remaining general-user community slash commands:

- `message_search` → `/search`
- `event_create` → `/event`
- `poll_create` → `/poll`

With this batch, all 18 top-level general slash capabilities from the A0 inventory are represented by a v4 capability specification.

## Layering

```text
LegacyGeneralCog
→ Release C/D GeneralCog strangler
→ Release E Community GeneralCog strangler
→ CapabilityDispatcher
→ CommunityCapabilityDataSource adapter
→ Discord API / channel history
```

## Safety boundaries

- `message_search` remains READ_ONLY but is not direct-executable from discovery because it requires arguments.
- `event_create` and `poll_create` remain WRITE_CONFIRM.
- Candidate selection never creates an event or poll.
- Natural-language event/poll creation requires requester-only input collection and a separate final confirmation.
- Release D's exact write-confirm set remains frozen; Release E extends it through a separate constant.
- EventView persistence/custom IDs remain unchanged.
- moderation/admin capabilities remain outside natural-language discovery.
- DB/schema, XP semantics, AI routing, Jev authority, memory retention, and persistent ticket contracts are unchanged.

## Batch gate

1. compileall PASS on Python 3.12 and 3.13;
2. full regression suite PASS;
3. Release D frozen-scope tests remain PASS;
4. Release E discovery policy audit PASS;
5. all 18 general slash capabilities are uniquely modeled;
6. event/poll are absent from direct-execution allowlist;
7. production boot preserves 19 synced top-level slash commands;
8. Human Verification checks `/event`, `/poll`, `/search`, natural-language event/poll confirmation, cancellation, and ordinary-chat false positives.
