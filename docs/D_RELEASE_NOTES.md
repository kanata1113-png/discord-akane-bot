# Release D — Batch 01 Release Notes

Natural-language capability discovery now includes three WRITE_CONFIRM capabilities: title change, conversation-history deletion, and reminder creation. These capabilities are never added to direct execution. Candidate selection enters a requester-only collection flow, and state mutation occurs only after a later explicit final confirmation that reuses the existing slash-command callback and CapabilityDispatcher path.

Release C read-only/direct-execution behavior remains unchanged.
