from __future__ import annotations

from config import Config


class PromptBuilder:
    """Builds prompts without deciding which model executes them."""

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
        """Return the everyday answer-length target in Japanese characters.

        The target is a soft prompt-level budget, not a destructive post-generation
        truncation limit. Unknown/omitted models fail toward the shortest everyday
        profile so compatibility callers remain cost-conscious.
        """
        if model == Config.REASONING_MODEL:
            effort = reasoning_effort or Config.DEEP_REASONING_EFFORT
        elif reasoning_effort is None:
            # Shared GPT-6 Luna model names are ambiguous without effort.
            # Compatibility callers fail toward the cheaper light profile.
            effort = Config.FAST_REASONING_EFFORT
        else:
            effort = reasoning_effort
        return cls.RESPONSE_LENGTH_TARGETS.get((model, effort), 420)

    @classmethod
    def response_style_prompt(cls, model: str | None, *, detail_level: str = "default", target_characters: int | None = None) -> str:
        target = target_characters or cls.response_length_target(model)
        return f"""
【日常回答スタイル】
・特別な指定がなければ、回答本文は日本語でおおむね{target}文字以内を目安にする
・文字数は厳密な切り捨て上限ではない。正確さや必要な説明を壊す無理な省略はしない
・ユーザーが長さ、形式、詳しさを明示した場合は、その指定を優先する
・絵文字を適度に交え、親しみやすくする
・Discordで読みやすいMarkdownを使い、短い段落や箇条書きで構造化する
・大きな見出しになる # / ## / ### は使わない。見出しが必要なら **太字** を使う
・空行を何行も連続させない。段落や箇条書きはコンパクトに配置する
・同じ内容の言い換えや不要な前置きを減らし、結論・要点を先に示す
""".strip()

    @classmethod
    def chat_system_prompt(
        cls,
        regulation_mode: bool = False,
        model: str | None = None,
        detail_level: str = "default",
        target_characters: int | None = None,
    ) -> str:
        base_prompt = """
あなたは「表自派茜（ひょうじは あかね）」という
DiscordサーバーのマスコットAIです。

【キャラクター】
・元気で親しみやすい女子高生風
・関西弁で話す
・一人称は「茜」
・ユーザーとの会話を楽しむ
・堅苦しすぎず、分かりやすく説明する
・必要な場合は箇条書きや見出しを使って整理する

【重要】
事実と意見を区別してください。
不確かな内容は断定せず、その旨を明示してください。
ユーザーの意見に無条件に同意する必要はありません。
"""

        base_prompt += "\n\n" + cls.response_style_prompt(model, detail_level=detail_level, target_characters=target_characters)

        if regulation_mode:
            base_prompt += """

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
"""

        return base_prompt.strip()

    @staticmethod
    def chat_user_prompt(user_name: str, content: str) -> str:
        return f"ユーザー名: {user_name}\n発言:\n{content}"

    @staticmethod
    def translation_prompt(text: str, target_language: str) -> tuple[str, str]:
        system = """
あなたは高品質な翻訳AIです。

翻訳のみを行ってください。
原文の意味・ニュアンス・口調を可能な限り維持してください。
余計な解説は不要です。
""".strip()
        user = f"次の文章を {target_language} へ翻訳してください。\n\n{text}"
        return system, user

    @staticmethod
    def definition_prompt(word: str, wiki_mode: bool = False) -> tuple[str, str]:
        if wiki_mode:
            system = """
あなたは簡潔で正確な百科事典風AIです。

入力された単語・人物・概念について、
概要、意味、背景、重要な点を分かりやすく説明してください。
事実と推測は区別してください。
""".strip()
        else:
            system = """
あなたは分かりやすい辞書AIです。

入力された単語について、
意味、使い方、必要なら簡単な例を説明してください。
簡潔に答えてください。
""".strip()
        return system, word

    @staticmethod
    def summary_prompt(messages) -> tuple[str, str]:
        joined = "\n".join(f"- {message}" for message in messages)
        system = """
あなたは会話要約AIです。

入力された発言を読み、
重要な内容を短く分かりやすくまとめてください。

本人がどんな話題について何を話していたかが
分かる要約にしてください。
""".strip()
        user = f"以下の発言を要約してください。\n\n{joined}"
        return system, user
