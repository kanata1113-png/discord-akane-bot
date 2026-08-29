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

        self.model = Config.CHAT_MODEL

    # ==========================================================================
    # Model Router
    # ==========================================================================

    def select_chat_model(
        self,
        content: str
    ) -> tuple[str, str]:

        text = content.lower()

        # 表現規制系は高性能モデル
        if any(
            keyword in content
            for keyword
            in Config.REGULATION_KEYWORDS
        ):

            return (
                Config.REASONING_MODEL,
                "regulation"
            )

        # 法律・分析・比較など
        if any(
            keyword.lower() in text
            for keyword
            in Config.REASONING_KEYWORDS
        ):

            return (
                Config.REASONING_MODEL,
                "reasoning"
            )

        # 長文質問は複雑な可能性が高い
        if len(content) >= 350:

            return (
                Config.REASONING_MODEL,
                "long-question"
            )

        return (
            Config.CHAT_MODEL,
            "normal-chat"
        )

    # ==========================================================================
    # OpenAI
    # ==========================================================================

    async def call_gpt(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 1000,
        history: list[dict] | None = None
    ) -> str:

        if not openai_client:

            return (
                "APIキーが設定されてへんで！"
            )

        model_lower = model.lower()

        is_reasoning = (
            "gpt-5" in model_lower
            or "o1" in model_lower
            or "o3" in model_lower
        )

        messages = [
            {
                "role": "system",
                "content": system
            }
        ]

        # 過去会話をsystemと今回のuserの間に入れる
        if history:

            for item in history:

                role = item.get(
                    "role"
                )

                content = item.get(
                    "content"
                )

                if (
                    role in {
                        "user",
                        "assistant"
                    }
                    and content
                ):

                    messages.append(
                        {
                            "role": role,
                            "content": content
                        }
                    )

        messages.append(
            {
                "role": "user",
                "content": user
            }
        )

        try:

            params = {
                "model": model,
                "messages": messages
            }

            if is_reasoning:

                params[
                    "max_completion_tokens"
                ] = max_tokens

                params[
                    "reasoning_effort"
                ] = "medium"

            else:

                params[
                    "max_tokens"
                ] = max_tokens

                params[
                    "temperature"
                ] = 0.7

            loop = asyncio.get_running_loop()

            response = await loop.run_in_executor(
                None,
                lambda: (
                    openai_client
                    .chat
                    .completions
                    .create(
                        **params
                    )
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

            return content.strip()

        except Exception as e:

            logger.exception(
                f"AI Error "
                f"(model={model}): {e}"
            )

            if (
                "timed out"
                in str(e).lower()
            ):

                return Config.TIMEOUT_MSG

            return Config.ERROR_MSG

    # ==========================================================================
    # Chat
    # ==========================================================================

    async def chat(
        self,
        user_name: str,
        content: str,
        history: list[dict] | None = None
    ) -> tuple[str, str, str]:

        model, route = self.select_chat_model(
            content
        )

        is_regulation = any(
            keyword in content
            for keyword
            in Config.REGULATION_KEYWORDS
        )

        if is_regulation:

            style = (
                "今は表現の自由・表現規制に関する話題です。"
                "関心を強く持ちながら話してください。"
                "ただし、事実と意見を区別し、"
                "ユーザーへ無条件に同意する必要はありません。"
            )

        else:

            style = (
                "親しみやすく、友達のような"
                "自然な関西弁で振る舞ってください。"
            )

        system = (
            "あなたは「表自派茜（ひょうじは あかね）」という"
            "元気な関西弁の女子高生AIです。\n"

            "一人称は「茜」。\n"

            f"現在話しているユーザー名は"
            f"「{user_name}」です。\n"

            f"{style}\n"

            "【会話について】\n"
            "過去の会話履歴が与えられている場合は、"
            "必要に応じて自然に参照してください。\n"
            "履歴に存在しない事実を"
            "『覚えている』と捏造してはいけません。\n"

            "【ルール】\n"
            "1. 日本語・自然な関西弁で話す。\n"
            "2. 回答は原則1000文字以内。\n"
            "3. 分からないことを知っているふりをしない。\n"
            "4. ユーザーの主張に無条件に同意しない。\n"
            "5. 事実と意見を可能な範囲で区別する。\n"
            "6. 会話履歴は会話を自然につなげる目的で使う。"
        )

        logger.info(
            "AI route | "
            f"user={user_name} | "
            f"model={model} | "
            f"route={route} | "
            f"history={len(history or [])}"
        )

        reply = await self.call_gpt(
            system=system,
            user=content,
            model=model,
            max_tokens=Config.NORMAL_CHAT_MAX_TOKENS,
            history=history
        )

        return (
            reply,
            model,
            route
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
            system=(
                f"Translate to {target_lang}. "
                "Output ONLY the translated text."
            ),
            user=text,
            model=Config.FAST_MODEL,
            max_tokens=1000
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
                "あなたはWikipedia風の"
                "要約アシスタントです。"
                f"「{word}」について、"
                "客観的な事実を中心に"
                "400文字以内で簡潔に説明してください。"
                "実際にWikipediaを閲覧したと"
                "偽ってはいけません。"
            )

        else:

            system = (
                "あなたは高性能な辞書です。"
                f"「{word}」という言葉の意味を、"
                "400文字以内で分かりやすく"
                "解説してください。"
            )

        system += (
            "\n必ず文章を完結させてください。"
        )

        return await self.call_gpt(
            system=system,
            user=word,
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
            system=(
                "以下の発言ログを"
                "400文字以内で要約してください。"
                "一人称は「茜」、"
                "自然な関西弁で。"
            ),
            user="\n".join(
                text_list
            ),
            model=Config.CHAT_MODEL,
            max_tokens=800
        )
