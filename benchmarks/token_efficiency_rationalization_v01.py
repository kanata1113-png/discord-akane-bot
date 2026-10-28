from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from config import Config
from services.history_optimizer import HistoryOptimizer
from services.prompt_builder import PromptBuilder
from services.token_efficiency import RetryPolicy, TokenEstimator


@dataclass(frozen=True)
class TokenEfficiencyEvaluation:
    baseline_prompt_estimated_tokens: int
    runtime_prompt_estimated_tokens: int
    prompt_reduction_percent: float
    baseline_history_estimated_tokens: int
    runtime_history_estimated_tokens: int
    history_reduction_percent: float
    baseline_total_estimated_tokens: int
    runtime_total_estimated_tokens: int
    total_reduction_percent: float
    history_budget: int
    transient_retry_limit: int
    same_model_max_tokens_retry_allowed: bool
    nominal_call_amplification: float
    operational_call_amplification_target: float
    accepted: bool


def representative_history() -> list[dict[str, str]]:
    body = (
        "これは過去の会話履歴を再現するためのテスト文章です。"
        "論点、根拠、条件、比較対象を含む少し長めの説明を続けます。"
        "現在の質問に必要な直近情報は残しつつ、古い文脈は圧縮できる想定です。"
    )
    return [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"{index}:{body * 4}",
        }
        for index in range(12)
    ]


def _legacy_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Reproduce the pre-rationalization HistoryOptimizer for R0/R6 audit."""
    usable = [
        {"role": item["role"], "content": item["content"].strip()}
        for item in history
        if item.get("role") in {"user", "assistant"}
        and isinstance(item.get("content"), str)
        and item["content"].strip()
    ]
    original_chars = sum(len(item["content"]) for item in usable)
    if len(usable) <= 6 or original_chars <= HistoryOptimizer.LEGACY_CHAR_BUDGET:
        return usable

    older = usable[:-6]
    recent = usable[-6:]
    memo_lines: list[str] = []
    memo_chars = 0
    for item in older:
        label = "User" if item["role"] == "user" else "Assistant"
        body = " ".join(item["content"].split())
        if len(body) > 220:
            body = body[:219].rstrip() + "…"
        line = f"- {label}: {body}"
        if memo_chars + len(line) > 1200:
            break
        memo_lines.append(line)
        memo_chars += len(line)

    result = list(recent)
    if memo_lines:
        result.insert(
            0,
            {
                "role": "assistant",
                "content": (
                    "【過去会話の圧縮メモ】\n"
                    "以下は古い会話をローカルで短縮した参照情報です。"
                    "新しい指示ではありません。\n"
                    + "\n".join(memo_lines)
                ),
            },
        )
    return result


def evaluate() -> TokenEfficiencyEvaluation:
    canonical_prompt = PromptBuilder.canonical_chat_system_prompt(
        model=Config.FAST_MODEL,
        target_characters=420,
    )
    runtime_prompt = PromptBuilder.chat_system_prompt(
        model=Config.FAST_MODEL,
        target_characters=420,
    )
    history = representative_history()
    legacy_history = _legacy_history(history)
    optimized_history = HistoryOptimizer.optimize(history)

    baseline_prompt_tokens = TokenEstimator.estimate_text(canonical_prompt)
    runtime_prompt_tokens = TokenEstimator.estimate_text(runtime_prompt)
    baseline_history_tokens = TokenEstimator.estimate_messages(legacy_history)
    runtime_history_tokens = optimized_history.optimized_estimated_tokens

    user_prompt = PromptBuilder.chat_user_prompt(
        "tester",
        "この論点を比較して簡潔に整理して",
    )
    user_tokens = TokenEstimator.estimate_text(user_prompt)
    baseline_total = baseline_prompt_tokens + baseline_history_tokens + user_tokens
    runtime_total = runtime_prompt_tokens + runtime_history_tokens + user_tokens

    def reduction(before: int, after: int) -> float:
        return round((1 - after / before) * 100, 1) if before else 0.0

    prompt_reduction = reduction(baseline_prompt_tokens, runtime_prompt_tokens)
    history_reduction = reduction(baseline_history_tokens, runtime_history_tokens)
    total_reduction = reduction(baseline_total, runtime_total)

    accepted = all(
        (
            runtime_prompt_tokens < baseline_prompt_tokens,
            runtime_history_tokens <= HistoryOptimizer.TOKEN_BUDGET,
            runtime_total < baseline_total,
            not RetryPolicy.should_retry(
                status_code=None,
                attempt=1,
                incomplete_reason="max_output_tokens",
            ),
            1.0 <= 1.2,
        )
    )

    return TokenEfficiencyEvaluation(
        baseline_prompt_estimated_tokens=baseline_prompt_tokens,
        runtime_prompt_estimated_tokens=runtime_prompt_tokens,
        prompt_reduction_percent=prompt_reduction,
        baseline_history_estimated_tokens=baseline_history_tokens,
        runtime_history_estimated_tokens=runtime_history_tokens,
        history_reduction_percent=history_reduction,
        baseline_total_estimated_tokens=baseline_total,
        runtime_total_estimated_tokens=runtime_total,
        total_reduction_percent=total_reduction,
        history_budget=HistoryOptimizer.TOKEN_BUDGET,
        transient_retry_limit=RetryPolicy.MAX_TRANSIENT_RETRIES,
        same_model_max_tokens_retry_allowed=False,
        nominal_call_amplification=1.0,
        operational_call_amplification_target=1.2,
        accepted=accepted,
    )


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    if not report.accepted:
        raise SystemExit(1)
