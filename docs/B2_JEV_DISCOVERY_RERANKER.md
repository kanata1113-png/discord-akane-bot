# B2 Jev Discovery Reranker

This slice adds an advisory Jev layer after the local capability shortlist.

```text
cheap local gate
→ local shortlist
→ Jev rerank (only when 2+ candidates)
→ candidate metadata
```

Jev receives only the user's short action-like message and the already-filtered candidate metadata. It never receives a dispatcher, handler, permission object, database object, or execution callback.

## Fail-safe behavior

The original local ordering is retained when:

- the API key is unavailable;
- the request times out or errors;
- Jev returns a capability not present in the local shortlist;
- confidence is below `JEV_DISCOVERY_CONFIDENCE` (default `0.75`).

A single local candidate skips Jev entirely.

The discovery timeout defaults to `1.0s` through `JEV_DISCOVERY_TIMEOUT_SECONDS`, independent of the existing model-routing timeout.

## Authority boundary

A valid Jev answer may only move one existing local candidate to the front. It cannot add a capability. In particular, moderation/admin actions cannot be injected by model output when they were absent from the local shortlist.

This PR still has no Discord `on_message` integration and no capability execution.
