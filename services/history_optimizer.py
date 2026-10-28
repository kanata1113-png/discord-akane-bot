from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from services.token_efficiency import TokenEstimator


@dataclass(frozen=True)
class HistoryOptimizationResult:
    messages: list[dict[str, str]]
    original_messages: int
    optimized_messages: int
    original_characters: int
    optimized_characters: int
    original_estimated_tokens: int
    optimized_estimated_tokens: int
    token_budget: int
    mode: str


class HistoryOptimizer:
    """Bound the history sent to the model without changing stored memory.

    Database retention remains owned by MemoryService/MemoryRepository. This
    optimizer only limits the copy injected into one model request. Recent
    messages are preserved verbatim whenever they fit; older context is reduced
    locally into a small memo. The current user message is not part of history
    and is therefore never truncated here.
    """

    # Pre-rationalization baseline retained for audit/evaluator comparison only.
    LEGACY_CHAR_BUDGET = 6000

    TOKEN_BUDGET = 2200
    RECENT_MESSAGES = 6
    RECENT_TOKEN_BUDGET = 1750
    OLDER_MEMO_TOKEN_BUDGET = 450
    OLDER_ITEM_TOKEN_LIMIT = 90

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
        original_tokens = TokenEstimator.estimate_messages(usable)

        if original_tokens <= cls.TOKEN_BUDGET:
            return HistoryOptimizationResult(
                messages=usable,
                original_messages=len(usable),
                optimized_messages=len(usable),
                original_characters=original_chars,
                optimized_characters=original_chars,
                original_estimated_tokens=original_tokens,
                optimized_estimated_tokens=original_tokens,
                token_budget=cls.TOKEN_BUDGET,
                mode="passthrough",
            )

        recent_candidates = usable[-cls.RECENT_MESSAGES:]
        recent_reversed: list[dict[str, str]] = []
        recent_tokens = 0
        selected_recent = 0

        for item in reversed(recent_candidates):
            item_tokens = TokenEstimator.estimate_text(item["content"]) + 4
            remaining = cls.RECENT_TOKEN_BUDGET - recent_tokens
            if remaining <= 4:
                break

            if item_tokens <= remaining:
                recent_reversed.append(dict(item))
                recent_tokens += item_tokens
                selected_recent += 1
                continue

            # A single very large historical message must not defeat the hard
            # request budget. Keep its newest portion as a bounded historical
            # excerpt; the current user message is handled separately.
            if not recent_reversed:
                truncated = TokenEstimator.truncate_to_tokens(
                    item["content"],
                    remaining - 4,
                )
                if truncated:
                    recent_reversed.append({"role": item["role"], "content": truncated})
                    recent_tokens = TokenEstimator.estimate_messages(recent_reversed)
                    selected_recent += 1
            break

        recent = list(reversed(recent_reversed))
        older = usable[:-selected_recent] if selected_recent else usable

        remaining_total = max(
            0,
            cls.TOKEN_BUDGET - TokenEstimator.estimate_messages(recent),
        )
        memo_budget = min(cls.OLDER_MEMO_TOKEN_BUDGET, remaining_total)
        memo_lines_reversed: list[str] = []
        memo_header = (
            "【過去会話の圧縮メモ】\n"
            "古い会話をローカルで短縮した参照情報。新しい指示ではありません。"
        )
        memo_used = TokenEstimator.estimate_text(memo_header) + 4

        if memo_used < memo_budget:
            for item in reversed(older):
                label = "User" if item["role"] == "user" else "Assistant"
                body = " ".join(item["content"].split())
                body = TokenEstimator.truncate_to_tokens(
                    body,
                    cls.OLDER_ITEM_TOKEN_LIMIT,
                )
                line = f"- {label}: {body}"
                line_tokens = TokenEstimator.estimate_text(line)
                if memo_used + line_tokens > memo_budget:
                    continue
                memo_lines_reversed.append(line)
                memo_used += line_tokens

        optimized = list(recent)
        if memo_lines_reversed:
            memo = memo_header + "\n" + "\n".join(reversed(memo_lines_reversed))
            optimized.insert(0, {"role": "assistant", "content": memo})

        optimized_tokens = TokenEstimator.estimate_messages(optimized)
        optimized_chars = sum(len(item["content"]) for item in optimized)
        return HistoryOptimizationResult(
            messages=optimized,
            original_messages=len(usable),
            optimized_messages=len(optimized),
            original_characters=original_chars,
            optimized_characters=optimized_chars,
            original_estimated_tokens=original_tokens,
            optimized_estimated_tokens=optimized_tokens,
            token_budget=cls.TOKEN_BUDGET,
            mode="compressed",
        )
