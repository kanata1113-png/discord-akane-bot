from __future__ import annotations

from dataclasses import dataclass

from services.akane_style_contract import StyleProfile


@dataclass(frozen=True)
class FewShotExample:
    key: str
    profile: StyleProfile
    feature: str
    user: str
    assistant: str


class AkaneFewShotBank:
    """Canonical few-shot registry.

    The infrastructure is intentionally empty in v0.1. Examples will be added
    only after the style insertion architecture is accepted. Keeping the bank
    separate from PromptBuilder lets examples evolve without touching routing,
    authorization, execution, or persistent data code.
    """

    MAX_EXAMPLES = 3
    EXAMPLES: tuple[FewShotExample, ...] = ()

    @classmethod
    def select(
        cls,
        profile: StyleProfile,
        *,
        feature: str | None = None,
        limit: int = MAX_EXAMPLES,
    ) -> tuple[FewShotExample, ...]:
        bounded_limit = max(0, min(limit, cls.MAX_EXAMPLES))
        matches = [
            example
            for example in cls.EXAMPLES
            if example.profile == profile
            and (feature is None or example.feature == feature)
        ]
        return tuple(matches[:bounded_limit])

    @classmethod
    def render(
        cls,
        profile: StyleProfile,
        *,
        feature: str | None = None,
        limit: int = MAX_EXAMPLES,
    ) -> str:
        examples = cls.select(profile, feature=feature, limit=limit)
        if not examples:
            return ""

        blocks = ["【文体例】"]
        for example in examples:
            blocks.append(
                f"User:\n{example.user}\n\nAssistant:\n{example.assistant}"
            )
        return "\n\n".join(blocks)
