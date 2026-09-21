# Release D WRITE_CONFIRM Security Notes

The Release D pilot intentionally separates discovery from authority.

- Discovery can surface `title_set`, `memory_forget`, and `remind`.
- `DIRECT_EXECUTION_CAPABILITY_IDS` remains unchanged for these IDs.
- Candidate selection is not confirmation.
- Argument/scope collection is not confirmation.
- A later destructive/final confirmation control is required.
- Every interactive view enforces requester identity.
- Existing slash callbacks remain the execution adapters, preserving existing validation and dispatcher confirmation semantics.
- Jev can rerank candidates but cannot authorize or execute the write.
- Cancellation stops the write flow without AI fallback for the consumed turn.
