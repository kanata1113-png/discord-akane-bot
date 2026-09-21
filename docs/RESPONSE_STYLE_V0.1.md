# Response Style v0.1

## Purpose

Reduce everyday response cost and improve Discord readability by coupling a soft answer-length profile to the model tier already selected by routing.

## Everyday length targets

These are prompt-level targets, not destructive post-generation truncation limits.

| Model tier | Model | Default answer-length target |
|---|---|---:|
| Default | Luna | ~420 Japanese characters |
| Standard work | Terra | ~840 Japanese characters |
| Promotion | Sol | ~1680 Japanese characters |

Explicit user requests for length, detail, or format override these defaults. Accuracy and necessary explanation take priority over forcing an answer under the target.

## Discord formatting

Normal chat responses should:

- use concise Markdown structure;
- use emoji in moderation;
- prefer short paragraphs and bullet lists;
- avoid large Markdown headings (`#`, `##`, `###`);
- use bold text for compact section labels when useful;
- avoid multiple consecutive blank lines;
- put conclusions and key points before secondary detail;
- avoid repetitive paraphrase and unnecessary preambles.

## Scope

This version changes prompt guidance only. It does not:

- truncate generated text after generation;
- change the routing taxonomy;
- change model assignment;
- change database/schema state;
- change Discord commands;
- change Railway configuration.

## Integration

`AIOrchestrator` passes the selected route model into `PromptBuilder.chat_system_prompt()`. `PromptBuilder` then injects the corresponding 420 / 840 / 1680 character everyday response profile.
