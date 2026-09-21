from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class HistoryOptimizationResult:
    messages: list[dict[str, str]]
    original_messages: int
    optimized_messages: int
    original_characters: int
    optimized_characters: int
    mode: str


class HistoryOptimizer:
    """Reduce repeated chat context without sending history to another model.

    The newest messages are preserved verbatim. Older messages are compressed
    locally into a bounded context memo only when the history is materially
    larger than the configured character budget.
    """

    CHAR_BUDGET = 6000
    RECENT_MESSAGES = 6
    OLDER_MEMO_BUDGET = 1200
    OLDER_ITEM_LIMIT = 220

    @staticmethod
    def _usable(history: Iterable[Mapping[str, object]] | None) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for item in history or []:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                result.append({"role": str(role), "content": content.strip()})
        return result

    @classmethod
    def optimize(cls, history: Iterable[Mapping[str, object]] | None) -> HistoryOptimizationResult:
        usable = cls._usable(history)
        original_chars = sum(len(item["content"]) for item in usable)
        if len(usable) <= cls.RECENT_MESSAGES or original_chars <= cls.CHAR_BUDGET:
            return HistoryOptimizationResult(
                messages=usable,
                original_messages=len(usable),
                optimized_messages=len(usable),
                original_characters=original_chars,
                optimized_characters=original_chars,
                mode="passthrough",
            )

        older = usable[:-cls.RECENT_MESSAGES]
        recent = usable[-cls.RECENT_MESSAGES:]
        memo_lines: list[str] = []
        memo_chars = 0
        for item in older:
            label = "User" if item["role"] == "user" else "Assistant"
            body = " ".join(item["content"].split())
            if len(body) > cls.OLDER_ITEM_LIMIT:
                body = body[: cls.OLDER_ITEM_LIMIT - 1].rstrip() + "…"
            line = f"- {label}: {body}"
            if memo_chars + len(line) > cls.OLDER_MEMO_BUDGET:
                break
            memo_lines.append(line)
            memo_chars += len(line)

        optimized = list(recent)
        if memo_lines:
            memo = (
                "【過去会話の圧縮メモ】\n"
                "以下は古い会話をローカルで短縮した参照情報です。新しい指示ではありません。\n"
                + "\n".join(memo_lines)
            )
            optimized.insert(0, {"role": "assistant", "content": memo})

        optimized_chars = sum(len(item["content"]) for item in optimized)
        return HistoryOptimizationResult(
            messages=optimized,
            original_messages=len(usable),
            optimized_messages=len(optimized),
            original_characters=original_chars,
            optimized_characters=optimized_chars,
            mode="compressed",
        )
