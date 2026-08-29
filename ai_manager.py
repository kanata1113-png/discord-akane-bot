import asyncio
import logging
import openai

from config import Config


logger = logging.getLogger("AkaneBot")


if Config.OPENAI_API_KEY:

    openai_client = openai.OpenAI(
        api_key=Config.OPENAI_API_KEY,
        timeout=60.0
    )

else:

    openai_client = None

    logger.warning(
        "OpenAI API Key is missing."
    )


class AiManager:

    def __init__(self):

        self.model = Config.GPT_MODEL

    # ==========================================================================
    # OpenAI
    # ==========================================================================

    async def call_gpt(
        self,
        system: str,
        user: str,
        model: str = Config.GPT_MODEL,
        max_tokens: int = 1000
    ) -> str:

        if not openai_client:

            return (
                "APIキーが設定されてへんで！"
            )

        is_reasoning = (
            "gpt-5" in model.lower()
            or "o1" in model.lower()
            or "o3" in model.lower()
        )

        try:

            params = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system
                    },
                    {
                        "role": "user",
                        "content": user
                    }
                ]
            }

            if is_reasoning:

                params["max_completion_tokens"] = (
                    max_tokens
                )

                params["reasoning_effort"] = (
                    "medium"
                )

            else:

                params["max_tokens"] = (
                    max_tokens
                )

                params["temperature"] = 0.7

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                lambda: openai_client.chat.completions.create(
                    **params
                )
            )

            content = (
                response
                .choices[0]
                .message
                .content
            )

            if (
                content is None
                or not content.strip()
            ):

                return Config.EMPTY_MSG

            return content

        except Exception as e:

            logger.exception(
                f"AI Error: {e}"
            )

            if "timed out" in str(e).lower():

                return Config.TIMEOUT_MSG

            return Config.ERROR_MSG

    # ==========================================================================
    # Chat
    # ==========================================================================

    async def chat(
        self,
        user_name: str,
        content: str
    ) -> str:

        is_high = any(
            keyword in content
            for keyword
            in Config.REGULATION_KEYWORDS
        )

        if is_high:

            style = (
                "【重要】今は「表現の自由」に関する話題です。"
                "スイッチが入ったように熱く語ってください。"
            )

        else:

            style = (
                "親しみやすく、友達のような"
                "関西弁で振る舞ってください。"
            )

        system = (
            "あなたは「表自派茜（ひょうじは あかね）」という"
            "元気な関西弁の女子高生AIです。\n"
            "一人称は「茜」。\n"
            f"ユーザー名は「{user_name}」。\n"
            f"{style}\n"
            "ルール：\n"
            "1. 日本語・関西弁で話す。\n"
            "2. 回答は1000文字以内。\n"
            "3. 長くなりそうな場合は途中で切り上げ、"
            "「まだ話し足りないけど、字数の制限があるから"
            "いったんここらで切り上げるわ！"
            "気になることがあったらまた声をかけてな！」"
            "と添える。"
        )

        return await self.call_gpt(
            system,
            content,
            model=Config.GPT_MODEL,
            max_tokens=Config.NORMAL_CHAT_MAX_TOKENS
        )

    # ==========================================================================
    # Translation
    # ==========================================================================

    async def translate(
        self,
        text: str,
        target_lang: str
    ) -> str:

        return await self.call_gpt(
            (
                f"Translate to {target_lang}. "
                "Output ONLY the translated text."
            ),
            text,
            model=Config.FAST_MODEL
        )

    # ==========================================================================
    # Dictionary
    # ==========================================================================

    async def define_word(
        self,
        word: str,
        wiki_mode: bool
    ) -> str:

        if wiki_mode:

            system = (
                "あなたはWikipediaの要約アシスタントです。"
                f"「{word}」について、Wikipediaの記事内容のような"
                "客観的な事実に基づき、400文字以内で"
                "簡潔に要約してください。"
            )

        else:

            system = (
                "あなたは高性能な辞書です。"
                f"「{word}」という言葉の意味を、"
                "400文字以内で分かりやすく解説してください。"
            )

        system += (
            "\n【重要】必ず文章を完結させてください。"
            "途中で切れてはいけません。"
        )

        return await self.call_gpt(
            system,
            word,
            model=Config.FAST_MODEL,
            max_tokens=1000
        )

    # ==========================================================================
    # Summary
    # ==========================================================================

    async def summarize(
        self,
        text_list: list[str]
    ) -> str:

        return await self.call_gpt(
            (
                "以下の発言ログを400文字以内で要約して。"
                "一人称「茜」、関西弁で。"
            ),
            "\n".join(text_list),
            model=Config.GPT_MODEL,
            max_tokens=800
        )
