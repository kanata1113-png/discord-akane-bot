# B2 Command Discovery Core

## Status

Prototype only. This slice does **not** connect discovery to `on_message`, does not call Jev, does not display a Discord panel, and cannot execute a capability.

## Pipeline introduced

```text
natural-language message
        ↓
cheap local gate
        ↓
local capability shortlist
        ↓
[future] Jev rerank only when ambiguity remains
        ↓
[future] Discord candidate panel
        ↓
[future] explicit user selection
        ↓
existing CapabilityDispatcher
```

## Safety boundary

Discovery returns metadata-only `DiscoveryCandidate` values. It receives no dispatcher and has no execution callback. Therefore a classification error cannot execute `/level`, `/fortune`, or any other capability in this slice.

Ordinary chat remains untouched because the prototype is not wired into `EventsCog.on_message`.

## Cost boundary

The local gate and shortlist use string matching only. No LLM/Jev request is made.

The intended next step is to add a small Jev reranker that receives only the local candidate shortlist rather than the full command catalog. Jev remains advisory: it may reorder/filter candidates but cannot dispatch them.

## Pilot catalog

The prototype currently operates against the six B1 progression specs:

- `/level`
- `/weekly`
- `/rankings`
- `/profile`
- `/achievements`
- `/fortune`

No moderation or admin capability participates in natural-language discovery.

## Fail-closed rules

The cheap gate rejects:

- empty text;
- messages longer than 180 characters;
- common analysis/question prefixes;
- messages with no action-like marker.

If the gate accepts but the local shortlist finds no capability, discovery returns `no_local_candidate` and normal chat remains the only available path.

## Next gate

Before Discord integration:

1. run CI and characterization;
2. add Jev reranking behind an injectable interface;
3. test timeout/error/low-confidence fallback to the local shortlist;
4. add candidate-panel rendering without execution;
5. only then consider read-only selection/execution.
