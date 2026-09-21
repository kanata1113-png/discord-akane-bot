# B2 Message Discovery Integration

This slice connects the previously isolated discovery layers to the existing AI-target message path.

```text
mention / configured auto-chat message
→ clean text
→ cheap local gate
→ local progression shortlist
→ optional Jev rerank
→ candidate panel
```

If the local gate rejects the message or finds no capability candidate, execution falls through to the existing daily-limit, memory, and AI chat path unchanged.

If discovery produces candidates, the bot replies with the selection-only panel and returns before AI chat. The panel still cannot execute a capability.

## Scope boundary

Discovery is evaluated only after the existing `is_target` check. Ordinary guild messages outside bot mentions / configured auto-chat channels do not trigger Jev discovery.

The integration does not:
- consume the AI daily limit for a discovered command panel;
- write AI conversation memory;
- increment AI chat count;
- execute a capability;
- expose moderation/admin actions.

## Telemetry

The integration logs metadata only:
- user ID;
- discovery source;
- candidate count.

Message text and Jev payload are not added to application logs by this slice.

## Human verification target

After CI and an explicitly approved deployment, test at least:
1. ordinary conversation still reaches AI;
2. `自分のレベルを見たい` shows a candidate panel;
3. `今週のXPランキングを見たい` shows weekly/ranking candidates;
4. clicking a candidate only shows the slash command and does not execute it;
5. another user cannot click the requester's panel.
