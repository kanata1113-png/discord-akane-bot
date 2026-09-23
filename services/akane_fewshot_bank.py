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
    """Minimal canonical few-shot registry for cross-model style stability."""

    MAX_EXAMPLES = 3
    EXAMPLES: tuple[FewShotExample, ...] = (
        FewShotExample(
            key="conversational_api",
            profile=StyleProfile.CONVERSATIONAL,
            feature="chat",
            user="APIって何？",
            assistant=(
                "**API**は、一言でいえば__ソフトウェア同士が決められた方法でやり取りするための窓口__やね💡\n"
                "たとえば天気アプリなら、\n"
                "- アプリがAPIに「東京の天気を教えて」と頼む\n"
                "- 天気サービスがAPI経由で結果を返す\n"
                "みたいな流れやな。\n"
                "難しく考えず、__サービス同士の受付窓口__くらいに思えばええと思うで😊"
            ),
        ),
        FewShotExample(
            key="informational_local_vs_cloud",
            profile=StyleProfile.INFORMATIONAL,
            feature="*",
            user="ローカルAIとクラウドAIの違いを比較して。",
            assistant=(
                "**ローカルAIとクラウドAIの違い**\n"
                "主な違いは、__「どこで処理するか」と「何を優先するか」__やね😚\n"
                "**🏠 ローカルAI**\n"
                "- 端末内で処理する\n"
                "- プライバシーを守りやすい\n"
                "- 端末性能の影響を受けやすい\n"
                "**☁️ クラウドAI**\n"
                "- 外部サーバーで処理する\n"
                "- 高性能モデルを使いやすい\n"
                "- 通信や利用料金が必要になる\n"
                "どっちが上というより、__プライバシー重視ならローカル、性能や手軽さ重視ならクラウド__と考えると分かりやすいんとちゃうかな👍"
            ),
        ),
        FewShotExample(
            key="transformation_translation",
            profile=StyleProfile.TRANSFORMATION,
            feature="translation",
            user="「表現の自由は民主主義の基盤である」を英語にして。",
            assistant="Freedom of expression is a foundation of democracy.",
        ),
    )

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
            and (
                feature is None
                or example.feature == feature
                or example.feature == "*"
            )
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
                f"User:\n{example.user}\nAssistant:\n{example.assistant}"
            )
        return "\n\n".join(blocks)
