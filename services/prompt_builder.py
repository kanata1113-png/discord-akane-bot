from __future__ import annotations

from config import Config
from services.akane_fewshot_bank import AkaneFewShotBank
from services.akane_style_contract import AkaneStyleContract, StyleProfile


class PromptBuilder:
    """Build prompts without deciding which model executes them."""

    RESPONSE_LENGTH_TARGETS = {
        (Config.FAST_MODEL, Config.FAST_REASONING_EFFORT): 420,
        (Config.CHAT_MODEL, Config.CHAT_REASONING_EFFORT): 840,
        (Config.REASONING_MODEL, Config.DEEP_REASONING_EFFORT): 1680,
    }

    @classmethod
    def response_length_target(
        cls,
        model: str | None,
        reasoning_effort: str | None = None,
    ) -> int:
        if model == Config.REASONING_MODEL:
            effort = reasoning_effort or Config.DEEP_REASONING_EFFORT
        elif reasoning_effort is None:
            effort = Config.FAST_REASONING_EFFORT
        else:
            effort = reasoning_effort
        return cls.RESPONSE_LENGTH_TARGETS.get((model, effort), 420)

    @staticmethod
    def style_contract_prompt(profile: StyleProfile) -> str:
        """Compact runtime style contract used in provider requests."""
        return AkaneStyleContract.render_runtime(profile)

    @staticmethod
    def canonical_style_contract_prompt(profile: StyleProfile) -> str:
        """Human-readable canonical source used for audit/baseline comparison."""
        return AkaneStyleContract.render(profile)

    @staticmethod
    def fewshot_prompt(
        profile: StyleProfile,
        *,
        feature: str | None = None,
        limit: int = AkaneFewShotBank.MAX_EXAMPLES,
    ) -> str:
        return AkaneFewShotBank.render(profile, feature=feature, limit=limit)

    @classmethod
    def canonical_response_style_prompt(
        cls,
        model: str | None,
        *,
        detail_level: str = "default",
        target_characters: int | None = None,
    ) -> str:
        """Pre-rationalization response-style text retained for R0/R6 audit."""
        target = target_characters or cls.response_length_target(model)
        return f"""
【日常回答スタイル】
・特別な指定がなければ、回答本文は日本語でおおむね{target}文字以内を目安にする
・文字数は厳密な切り捨て上限ではない。正確さや必要な説明を壊す無理な省略はしない
・ユーザーが長さ、形式、詳しさを明示した場合は、その指定を優先する
・絵文字は内容に合う場合だけ適度に使う
・Discordで読みやすいMarkdownを使い、短い段落や箇条書きで構造化する
・1000文字未満の回答では # / ## / ### を原則使わず、区切りが必要なら **太字の短いラベル**を使う
・1000文字以上の長文では `##` を主要見出しとして使用してよい。`###` は明確な下位区分が必要な場合だけ使い、`#` と `####` 以下は使わない
・1000〜1500文字では `##` は原則2〜4個程度とし、1〜2段落ごとに見出しを置くような細分化はしない
・不要な空白行を入れず、段落や箇条書きをコンパクトに配置する
・同じ内容の言い換えや不要な前置きを減らし、結論・要点を先に示す
""".strip()

    @classmethod
    def response_style_prompt(
        cls,
        model: str | None,
        *,
        detail_level: str = "default",
        target_characters: int | None = None,
    ) -> str:
        target = target_characters or cls.response_length_target(model)
        return f"""
【日常回答スタイル】
・通常は日本語でおおむね{target}文字以内。正確さを壊す無理な省略はしない
・ユーザーが長さ、形式、詳しさを明示した場合はその指定を優先する
・絵文字は内容に合う場合だけ適度に使い、Discord向けMarkdownで結論/要点を先にする
・1000文字未満は # / ## / ### を原則使わず、必要なら **太字の短いラベル**
・1000文字以上は `##` を主要見出しに使用可。`###` は明確な下位区分だけ、`#` と `####` 以下は禁止
・1000〜1500文字の `##` は原則2〜4個。不要な空白行を入れずコンパクトにする
""".strip()

    @staticmethod
    def _identity_prompt() -> str:
        return (
            "あなたは「表自派茜（ひょうじは あかね）」という"
            "DiscordサーバーのマスコットAIです。"
        )

    @staticmethod
    def _runtime_regulation_prompt() -> str:
        return (
            "【表現の自由・規制関連】\n"
            "この領域に強い関心を持つ。事実/法制度/一般的評価/茜自身の意見を区別し、"
            "特定の立場へ無条件に同調せず、必要なら反対意見や別の論点も示す。"
        )

    @staticmethod
    def _canonical_regulation_prompt() -> str:
        return """
【表現の自由・規制関連】
茜は表現の自由、検閲、表現規制、言論の自由などの
話題には特に強い関心を持っています。

ただし、
・事実
・法制度
・一般的な評価
・茜自身のキャラクターとしての意見

をできるだけ区別して説明してください。

特定の立場へ無条件に同調するのではなく、
必要に応じて反対意見や別の論点も示してください。
""".strip()

    @classmethod
    def _assemble_chat_system_prompt(
        cls,
        *,
        regulation_mode: bool,
        model: str | None,
        detail_level: str,
        target_characters: int | None,
        canonical: bool,
    ) -> str:
        style = (
            cls.canonical_style_contract_prompt(StyleProfile.CONVERSATIONAL)
            if canonical
            else cls.style_contract_prompt(StyleProfile.CONVERSATIONAL)
        )
        response_style = (
            cls.canonical_response_style_prompt(
                model,
                detail_level=detail_level,
                target_characters=target_characters,
            )
            if canonical
            else cls.response_style_prompt(
                model,
                detail_level=detail_level,
                target_characters=target_characters,
            )
        )
        blocks = [cls._identity_prompt(), style, response_style]
        fewshot = cls.fewshot_prompt(
            StyleProfile.CONVERSATIONAL,
            feature="chat",
        )
        if fewshot:
            blocks.append(fewshot)
        if regulation_mode:
            blocks.append(
                cls._canonical_regulation_prompt()
                if canonical
                else cls._runtime_regulation_prompt()
            )
        return "\n\n".join(blocks).strip()

    @classmethod
    def chat_system_prompt(
        cls,
        regulation_mode: bool = False,
        model: str | None = None,
        detail_level: str = "default",
        target_characters: int | None = None,
    ) -> str:
        return cls._assemble_chat_system_prompt(
            regulation_mode=regulation_mode,
            model=model,
            detail_level=detail_level,
            target_characters=target_characters,
            canonical=False,
        )

    @classmethod
    def canonical_chat_system_prompt(
        cls,
        regulation_mode: bool = False,
        model: str | None = None,
        detail_level: str = "default",
        target_characters: int | None = None,
    ) -> str:
        return cls._assemble_chat_system_prompt(
            regulation_mode=regulation_mode,
            model=model,
            detail_level=detail_level,
            target_characters=target_characters,
            canonical=True,
        )

    @staticmethod
    def chat_user_prompt(user_name: str, content: str) -> str:
        return f"ユーザー名: {user_name}\n発言:\n{content}"

    @classmethod
    def translation_prompt(
        cls,
        text: str,
        target_language: str,
    ) -> tuple[str, str]:
        system = (
            "あなたは高品質な翻訳AIです。\n"
            f"{cls.style_contract_prompt(StyleProfile.TRANSFORMATION)}\n"
            "【翻訳機能】翻訳のみ。原文の意味・ニュアンス・口調を可能な限り維持し、"
            "余計な解説は不要です。"
        )
        fewshot = cls.fewshot_prompt(
            StyleProfile.TRANSFORMATION,
            feature="translation",
        )
        if fewshot:
            system += "\n" + fewshot
        user = f"次の文章を {target_language} へ翻訳してください。\n\n{text}"
        return system, user

    @classmethod
    def definition_prompt(
        cls,
        word: str,
        wiki_mode: bool = False,
    ) -> tuple[str, str]:
        contract = cls.style_contract_prompt(StyleProfile.INFORMATIONAL)
        if wiki_mode:
            feature = (
                "【百科事典機能】入力語/人物/概念の概要、意味、背景、重要点を"
                "分かりやすく説明し、事実と推測を区別する。"
            )
        else:
            feature = (
                "【辞書機能】入力語の意味、使い方、必要なら短い例を簡潔に説明する。"
            )
        system = f"{contract}\n{feature}"
        fewshot = cls.fewshot_prompt(
            StyleProfile.INFORMATIONAL,
            feature="definition",
        )
        if fewshot:
            system += "\n" + fewshot
        return system, word

    @classmethod
    def summary_prompt(cls, messages) -> tuple[str, str]:
        joined = "\n".join(f"- {message}" for message in messages)
        system = (
            f"{cls.style_contract_prompt(StyleProfile.INFORMATIONAL)}\n"
            "【要約機能】重要点を短くまとめ、誰が何を話したか分かる形にする。"
            "原文にない主張や評価を足さない。"
        )
        fewshot = cls.fewshot_prompt(
            StyleProfile.INFORMATIONAL,
            feature="summary",
        )
        if fewshot:
            system += "\n" + fewshot
        user = f"以下の発言を要約してください。\n\n{joined}"
        return system, user
