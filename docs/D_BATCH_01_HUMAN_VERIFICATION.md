# Release D — Human Verification Checklist

Run after aggregate CI passes and production boots successfully.

1. `称号を変更して` → Candidate Panel → `称号変更` → modal → review → final confirm → existing `/title_set` behavior.
2. Cancel at Candidate Panel, write-entry, or final confirmation → no state change.
3. `記憶を消して` → Candidate Panel → `会話履歴削除` → choose current/all scope → destructive confirmation → existing `/forget` behavior.
4. `リマインダーを登録したい` → Candidate Panel → input minutes/message → review → final confirm → existing `/remind` behavior.
5. Invalid reminder minutes are rejected before final confirmation.
6. Another user cannot operate the requester's write controls.
7. `称号を見たい` still routes to read-only titles rather than title_set.
8. `メモリーを確認したい` still routes to memory_status rather than deletion.
9. Ordinary explanatory chat such as `記憶について教えて` stays on AI chat.
10. Existing read-only direct execution (`level`, `leaderboard`, `weekly`, `profile`, `achievements`, `memory_status`) still works.
