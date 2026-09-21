# B2 Discord Candidate Panel

This slice adds the Discord UI surface for capability discovery without connecting it to message routing yet.

The panel accepts at most four `DiscoveryCandidate` objects and renders one button per candidate.

## Execution boundary

The View has no `CapabilityDispatcher`, no handler callback, and no database reference. Selecting a button only records the selected capability metadata and edits the panel to show the corresponding existing slash command.

The UI explicitly states that selection does not automatically execute the command.

Only the user who requested the panel may select a candidate; other users receive an ephemeral rejection.

## Integration sequence

The next slice may connect:

```text
message
→ local gate
→ local shortlist
→ optional Jev rerank
→ candidate panel
```

That integration must still stop before capability execution. Existing AI chat should remain the fallback whenever discovery rejects the message or finds no candidates.

Only after human verification of false-positive behavior should read-only panel selection be considered for direct execution.
