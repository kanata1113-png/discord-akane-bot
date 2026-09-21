# Release D — WRITE_CONFIRM Waterfall

## Goal

Promote a small set of already-migrated WRITE_CONFIRM capabilities into natural-language discovery without weakening the Release C direct-execution boundary.

Pilot set:

- `title_set`
- `memory_forget`
- `remind`

## Interaction contract

```text
natural-language request
→ local discovery
→ Candidate Panel
→ requester explicitly selects WRITE_CONFIRM capability
→ requester-only argument/scope collection
→ final confirmation
→ existing GeneralCog slash callback
→ existing CapabilityDispatcher
→ existing handler / DB behavior
```

No write occurs at candidate selection time.

## Capability-specific flow

### title_set

Candidate selection opens a dedicated entry step. The user provides the title key in a Discord modal. The submitted value is displayed back to the user and requires a second explicit `称号変更を確定` action before the existing `/title_set` callback is invoked.

### memory_forget

Candidate selection asks whether to delete history for the current channel or all channels. Scope selection is not execution. A separate destructive `削除を確定` action is required before the existing `/forget` callback runs.

### remind

Candidate selection opens a modal for minutes and message text. Local validation keeps minutes in the existing 1–10080 range and message length within 500 characters. Submission only creates a confirmation panel; `登録を確定` is required before the existing `/remind` callback runs.

## Safety boundaries

- requester-only at every view stage;
- explicit cancellation at entry and confirmation stages;
- WRITE_CONFIRM IDs remain disjoint from `DIRECT_EXECUTION_CAPABILITY_IDS`;
- no moderation/admin discovery;
- no DB/schema change;
- no XP change;
- no AI model-routing change;
- no Jev authorization role;
- existing slash callbacks remain the Discord execution adapters.

## Release gate

1. full Python 3.12/3.13 CI passes;
2. Release C policy audit remains valid or is intentionally extended for Release D;
3. no WRITE_CONFIRM capability enters the direct-execution allowlist;
4. production boots with 19 slash commands and existing persistent state;
5. Human Verification covers cancel, title change, scoped forget, reminder registration, and ordinary-chat false positives.
