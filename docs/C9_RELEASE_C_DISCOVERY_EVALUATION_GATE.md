# Release C9 — Discovery Evaluation Gate

## Purpose

The Release C discovery vocabulary is broader than B2, so regression coverage
must test both recall and false-positive behavior across the expanded surface.

## Positive corpus

The gate covers:

- level
- leaderboard
- weekly
- rankings
- profile
- achievements
- fortune
- titles
- memory status
- translate
- summary
- define

## Negative corpus

The gate protects ordinary conversation and unsupported write intents, including:

- explanatory / analytical discussion about capability-like words;
- title change/equip requests while `title_set` discovery is not approved;
- memory deletion requests while `memory_forget` discovery is not approved;
- reminder creation while write-capability discovery is not approved.

## Repair discovered by the batch

Vocabulary expansion exposed two false-positive classes:

```text
称号を変更して  -> could incorrectly suggest read-only titles
記憶を消して    -> could incorrectly suggest memory_status
```

C9 adds a cheap local unsupported-write guard. These requests remain outside the
Candidate Panel until a dedicated WRITE_CONFIRM discovery/confirmation flow is
implemented.

## Invariants

- no write capability is silently promoted;
- no change to direct-execution allowlist;
- chat/explanation fallback remains intact;
- no AI routing, DB/schema or permission change.
