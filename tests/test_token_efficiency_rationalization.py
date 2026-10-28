from __future__ import annotations

from types import SimpleNamespace

import pytest

from benchmarks.token_efficiency_rationalization_v01 import evaluate
from config import Config
from services.ai_executor import AIExecutor
from services.cost_telemetry import CostTelemetry, UsageEvent
from services.history_optimizer import HistoryOptimizer
from services.prompt_builder import PromptBuilder
from services.token_efficiency import RetryPolicy, TokenEstimator


def test_runtime_prompt_is_smaller_but_keeps_style_anchors():
    canonical = PromptBuilder.canonical_chat_system_prompt(
        model=Config.FAST_MODEL,
        target_characters=420,
    )
    runtime = PromptBuilder.chat_system_prompt(
        model=Config.FAST_MODEL,
        target_characters=420,
    )
    assert TokenEstimator.estimate_text(runtime) < TokenEstimator.estimate_text(canonical)
    assert "文体プロファイル: CONVERSATIONAL" in runtime
    assert "一人称は「茜」" in runtime
    assert "【文体例】" in runtime
    assert "APIって何？" in runtime
    assert "1000文字未満" in runtime
    assert "主要見出し" in runtime


def test_history_optimizer_caps_only_injected_history():
    history = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"{index}:" + ("日本語の長い会話履歴です。" * 80),
        }
        for index in range(12)
    ]
    result = HistoryOptimizer.optimize(history)
    assert result.mode == "compressed"
    assert result.original_messages == 12
    assert result.optimized_estimated_tokens <= HistoryOptimizer.TOKEN_BUDGET
    assert result.optimized_estimated_tokens < result.original_estimated_tokens
    assert result.messages[-1]["content"] == history[-1]["content"]
    assert "過去会話の圧縮メモ" in result.messages[0]["content"]


def test_retry_policy_never_retries_max_tokens_and_caps_transient_retry():
    assert not RetryPolicy.should_retry(
        status_code=None,
        attempt=1,
        incomplete_reason="max_output_tokens",
    )
    assert RetryPolicy.should_retry(status_code=429, attempt=1)
    assert RetryPolicy.should_retry(status_code=503, attempt=1)
    assert not RetryPolicy.should_retry(status_code=429, attempt=2)
    assert not RetryPolicy.should_retry(status_code=400, attempt=1)


def test_cost_telemetry_separates_logical_requests_and_model_calls():
    telemetry = CostTelemetry()
    telemetry.record(
        UsageEvent(
            Config.FAST_MODEL,
            "normal-chat",
            100,
            40,
            140,
            logical_request_id="r1",
            feature="chat",
            call_kind="primary",
            estimated_input_tokens=120,
        )
    )
    telemetry.record(
        UsageEvent(
            Config.FAST_MODEL,
            "normal-chat",
            100,
            40,
            140,
            logical_request_id="r2",
            feature="chat",
            call_kind="primary",
            estimated_input_tokens=120,
        )
    )
    telemetry.record(
        UsageEvent(
            Config.FAST_MODEL,
            "normal-chat",
            100,
            40,
            140,
            logical_request_id="r2",
            feature="chat",
            call_kind="retry",
            attempt=2,
            estimated_input_tokens=120,
        )
    )
    summary = telemetry.summary()
    assert summary["logical_requests"] == 2
    assert summary["model_calls"] == 3
    assert summary["retry_failover_calls"] == 1
    assert summary["call_amplification"] == 1.5
    assert summary["by_feature"]["chat"]["logical_requests"] == 2
    assert summary["by_feature"]["chat"]["model_calls"] == 3


class _FakeResponses:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        item = self.sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeClient:
    def __init__(self, sequence):
        self.responses = _FakeResponses(sequence)


class _TransientError(Exception):
    status_code = 429


def _usage(input_tokens=100, output_tokens=20):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


@pytest.mark.asyncio
async def test_executor_does_not_repeat_max_tokens_incomplete():
    response = SimpleNamespace(
        status="incomplete",
        output_text="partial",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=_usage(),
    )
    telemetry = CostTelemetry()
    client = _FakeClient([response])
    executor = AIExecutor(client, cost_telemetry=telemetry)

    result = await executor.generate(
        system="system",
        user="user",
        model=Config.FAST_MODEL,
        max_tokens=100,
        reasoning_effort=Config.FAST_REASONING_EFFORT,
        route="normal-chat",
        feature="chat",
    )

    assert client.responses.calls == 1
    assert "partial" in result
    summary = telemetry.summary()
    assert summary["logical_requests"] == 1
    assert summary["model_calls"] == 1
    assert summary["max_tokens_incomplete"] == 1
    assert summary["same_model_max_tokens_retry"] == 0


@pytest.mark.asyncio
async def test_executor_retries_transient_http_once_and_records_amplification():
    response = SimpleNamespace(
        status="completed",
        output_text="ok",
        incomplete_details=None,
        usage=_usage(),
    )
    telemetry = CostTelemetry()
    client = _FakeClient([_TransientError("rate"), response])
    executor = AIExecutor(client, cost_telemetry=telemetry)

    result = await executor.generate(
        system="system",
        user="user",
        model=Config.FAST_MODEL,
        max_tokens=100,
        reasoning_effort=Config.FAST_REASONING_EFFORT,
        route="normal-chat",
        feature="chat",
    )

    assert result == "ok"
    assert client.responses.calls == 2
    summary = telemetry.summary()
    assert summary["logical_requests"] == 1
    assert summary["model_calls"] == 2
    assert summary["retry_failover_calls"] == 1
    assert summary["call_amplification"] == 2.0


def test_r6_static_before_after_evaluation_passes():
    report = evaluate()
    assert report.accepted
    assert report.runtime_prompt_estimated_tokens < report.baseline_prompt_estimated_tokens
    assert report.runtime_history_estimated_tokens <= report.history_budget
    assert report.runtime_total_estimated_tokens < report.baseline_total_estimated_tokens
    assert not report.same_model_max_tokens_retry_allowed
    assert report.operational_call_amplification_target == 1.2
