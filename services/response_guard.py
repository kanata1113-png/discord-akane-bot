from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseCheck:
    ok: bool
    reason: str | None = None


class ResponseGuard:
    """Deterministic, no-LLM response checks.

    The guard detects mechanical output failures only. It deliberately does not
    grade factual correctness, political viewpoint, style quality, or semantic
    completeness beyond explicit structural requests.
    """

    @staticmethod
    def _has_unclosed_code_fence(body: str) -> bool:
        return body.count("```") % 2 == 1

    @staticmethod
    def _missing_requested_structure(body: str, requested_format: str | None) -> str | None:
        if requested_format == "bullets":
            lines = [line.lstrip() for line in body.splitlines() if line.strip()]
            if not any(line.startswith(("- ", "* ", "• ")) for line in lines):
                return "missing_bullets"
        elif requested_format == "table":
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            if not any("|" in line for line in lines):
                return "missing_table"
        elif requested_format == "code" and "```" not in body:
            return "missing_code_block"
        return None

    @classmethod
    def check(
        cls,
        text: str,
        *,
        incomplete: bool = False,
        requested_format: str | None = None,
    ) -> ResponseCheck:
        body = (text or "").strip()
        if incomplete:
            return ResponseCheck(False, "incomplete")
        if not body:
            return ResponseCheck(False, "empty")
        if len(body) < 2:
            return ResponseCheck(False, "too_short")
        if cls._has_unclosed_code_fence(body):
            return ResponseCheck(False, "unclosed_code_fence")
        structure_reason = cls._missing_requested_structure(body, requested_format)
        if structure_reason:
            return ResponseCheck(False, structure_reason)
        return ResponseCheck(True, None)
