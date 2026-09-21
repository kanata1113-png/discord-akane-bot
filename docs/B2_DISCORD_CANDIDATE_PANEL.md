# B2 Discord Candidate Panel

This slice introduced the Discord UI surface for natural-language capability discovery.

The panel accepts at most four `DiscoveryCandidate` objects and renders one button per candidate plus an explicit cancel button.

## Current execution boundary

Discovery and reranking are still non-executing. A capability can run only after the requester explicitly presses its candidate button.

Direct execution is further restricted by `services/discovery_direct_execution.py`:

- `level`
- `weekly`
- `profile` (requester as the default target)
- `achievements` (requester as the default target)

These selections reuse the established Discord slash-command callbacks so the existing presentation, error handling, and progression bookkeeping contracts remain authoritative.

The following discovered candidates remain guidance-only:

- `rankings`: its required `category` argument is not represented by `DiscoveryCandidate`, so B2 does not guess it.
- `fortune`: first access persists the daily fortune and progression bookkeeping, so it is excluded from the direct-read path.
- any future non-allowlisted capability, including moderation/admin actions.

Unsupported selections terminate by showing the existing slash command. They do not fall back into AI chat.

## Requester and cancellation boundary

Only the user who requested the panel may select or cancel it; other users receive an ephemeral rejection.

Cancellation is explicit user cancellation, separate from timeout. It:

- executes no capability;
- does not fall back to AI chat;
- disables all panel controls;
- marks the panel as cancelled;
- stops the view.

## Message-flow boundary

```text
message
→ cheap local gate
→ local shortlist
→ optional Jev rerank
→ candidate panel
→ explicit requester selection
   ├─ allowlisted argument-complete READ_ONLY → direct execution
   ├─ other candidate → slash-command guidance only
   └─ cancel → stop
```

A panel being shown still terminates the normal message-routing branch. Ordinary AI chat remains the fallback only when discovery rejects the original message or produces no candidate panel.
