# AI Platform v1.3.2 — Continuity Floor

## Purpose

v1.3.2 hardens follow-up routing when Jev returns a low-confidence result.

## Behavior

A continuity floor is applied only when all of the following are true:

- the current message is a detected follow-up
- Jev rejected the decision because confidence was below threshold
- the current Legacy route would be `normal-chat`
- the recent conversation anchor was `reasoning` or `deep-reasoning`

In that narrow case the selected route is floored at the anchor route instead of dropping to `normal-chat`.

High-confidence Jev decisions are never overridden by this floor. Router/API errors such as timeouts also continue to use the existing Legacy fallback rather than the continuity floor.

## Chained follow-ups

When recent user turns are themselves follow-up messages, routing metadata is anchored to the nearest earlier non-follow-up user turn. This lets chains such as:

```text
analysis request -> follow-up -> follow-up
```

retain the original analytical routing context without sending prior message bodies to Jev.

## Privacy

Prior conversation text remains local. Jev receives only privacy-minimal derived labels such as:

```text
followup:true
previous_route:reasoning
previous_intent:analysis
```

No Discord identity fields are added.

## Safety

- no DB/schema change
- no change to specialized command paths
- `JEV_ROUTER_CONTEXT_HINTS` remains the feature gate
- `AI_ADAPTIVE_TOKEN_BUDGET` remains independent
- continuity floor applies only to low-confidence Jev rejection, not accepted Jev routes or API errors
