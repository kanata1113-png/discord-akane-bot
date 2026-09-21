from __future__ import annotations


class IntentGate:
    """Deterministic intent hinting for telemetry and future dispatch.

    v1.4 is observational only: it does not redirect normal chat into slash
    command pipelines.
    """

    TRANSLATION_MARKERS = ("翻訳", "訳して", "translate", "translation")
    SUMMARY_MARKERS = ("要約", "まとめて", "summarize", "summary")
    DEFINITION_MARKERS = ("意味", "定義", "とは", "define", "definition")
    ANALYSIS_MARKERS = (
        "比較",
        "分析",
        "原因",
        "検討",
        "論点",
        "compare",
        "analyze",
        "analysis",
    )

    @classmethod
    def classify(cls, content: str) -> str:
        text = (content or "").strip().lower()
        if any(marker in text for marker in cls.TRANSLATION_MARKERS):
            return "translation-like"
        if any(marker in text for marker in cls.SUMMARY_MARKERS):
            return "summary-like"
        if any(marker in text for marker in cls.DEFINITION_MARKERS):
            return "definition-like"
        if any(marker in text for marker in cls.ANALYSIS_MARKERS):
            return "analysis"
        if text.endswith("?") or text.endswith("？"):
            return "question"
        return "casual-chat"
