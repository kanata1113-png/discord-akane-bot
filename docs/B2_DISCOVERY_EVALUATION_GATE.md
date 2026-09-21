# B2 Candidate Discovery — Integration Evaluation Gate

## Purpose

B2 is now connected end-to-end through the candidate-panel boundary:

```text
bot-target message
→ cheap local gate
→ local shortlist
→ optional Jev rerank
→ candidate panel
→ explicit user selection
→ slash-command guidance only
```

No natural-language capability execution exists yet.

## Automated evaluation corpus

A compact regression corpus is included to test the highest-risk product failure: ordinary conversation being intercepted as a command request.

### Expected discovery

- 自分のレベルを見たい → level
- レベルを確認したい → level
- 今週のXPランキングを見たい → weekly
- ランキングを表示して → rankings
- プロフィールを表示したい → profile
- 実績を確認したい → achievements
- 今日の運勢を占いたい → fortune

### Expected ordinary chat

- 今日はいい天気だね
- どう思う？
- なぜランキング制度が必要なの？
- レベルの高い議論だね
- プロフィール記事について分析して
- 実績のある政治家について教えて
- 運勢って科学的に意味あるの？
- XPという言葉の意味を教えて
- ランキング文化についてどう思う？
- 今週は忙しかった

The negative set deliberately includes lexical collisions with capability terms.

## Promotion criteria

B2 may proceed to an explicitly approved production/human-verification deployment only when:

1. repository CI is green on Python 3.12 and 3.13;
2. all evaluation-corpus cases pass;
3. candidate selection remains non-executing;
4. moderation/admin capabilities remain absent;
5. no DB/schema or AI-routing semantics changed.

## Human verification

After deployment approval, verify in Discord:

- ordinary conversation reaches the normal AI path;
- each positive example produces sensible candidates;
- ambiguous weekly/ranking requests produce useful ordering;
- another user cannot operate the requester's panel;
- selecting a candidate does not execute it;
- no discovery panel appears for lexical-collision negative examples.

## Next architectural decision

Do not move directly from this gate to unrestricted natural-language execution.

If human verification passes, the next safe slice is **read-only explicit-selection execution** for the B1 progression pilot. The button selection itself becomes the user's execution intent, while the dispatcher remains the sole execution authority.

`fortune` should be reviewed separately because a first daily lookup can create persistent state even though its user-facing policy is read-like.
