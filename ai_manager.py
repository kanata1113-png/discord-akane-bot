import asyncio
import logging

from openai import AsyncOpenAI

from config import Config
from services.jev_model_router import JevModelRouter


logger = logging.getLogger(
    "AkaneBot"
)


class AiManager:

    def __init__(
        self
    ):

        self.client = AsyncOpenAI(
            api_key=Config.OPENAI_API_KEY
        )
        self.jev_router = JevModelRouter.from_environment()
        self._jev_shadow_tasks = set()

        logger.info(
            "JEV router initialized | mode=%s | configured=%s | "
            "confidence_threshold=%.2f | timeout_seconds=%.2f",
            self.jev_router.mode,
            self.jev_router.is_configured,
            self.jev_router.confidence_threshold,
            self.jev_router.timeout_seconds,
        )

    # ==========================================================================
    # System Prompt
    # ==========================================================================

    @staticmethod
    def get_system_prompt(
        regulation_mode: bool = False
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

    # ==========================================================================
    # Model Routing - V34 legacy router
    # ==========================================================================

    def select_chat_model(
        self,
        content: str
    ) -> tuple[str, str, str]:

        text = (
            content
            or ""
        ).strip()

        # ======================================================================
        # Deep Reasoning
        # ======================================================================

        if any(
            keyword in text
            for keyword
            in Config.DEEP_REASONING_KEYWORDS
        ):

            return (
                Config.REASONING_MODEL,
                Config.DEEP_REASONING_EFFORT,
                "deep-reasoning"
            )

        # ======================================================================
        # Regulation
        # ======================================================================

        if any(
            keyword in text
            for keyword
            in Config.REGULATION_KEYWORDS
        ):

            return (
                Config.REASONING_MODEL,
                Config.REASONING_EFFORT,
                "regulation"
            )

        # ======================================================================
        # General Reasoning
        # ======================================================================

        if any(
            keyword in text
            for keyword
            in Config.REASONING_KEYWORDS
        ):

            return (
                Config.REASONING_MODEL,
                Config.REASONING_EFFORT,
                "reasoning"
            )

        # ======================================================================
        # Long Question
        # ======================================================================

        if len(text) >= 350:

            return (
                Config.REASONING_MODEL,
                Config.REASONING_EFFORT,
                "long-question"
            )

        # ======================================================================
        # Normal Chat
        # ======================================================================

        return (
            Config.CHAT_MODEL,
            Config.CHAT_REASONING_EFFORT,
            "normal-chat"
        )

    @staticmethod
    def _normalize_legacy_route_for_jev(route: str) -> str:
        if route == "deep-reasoning":
            return "deep-reasoning"
        if route in {"regulation", "reasoning", "long-question"}:
            return "reasoning"
        return "normal-chat"

    @staticmethod
    def _route_config(route: str) -> tuple[str, str]:
        if route == "deep-reasoning":
            return (
                Config.REASONING_MODEL,
                Config.DEEP_REASONING_EFFORT,
            )
        if route == "reasoning":
            return (
                Config.REASONING_MODEL,
                Config.REASONING_EFFORT,
            )
        return (
            Config.CHAT_MODEL,
            Config.CHAT_REASONING_EFFORT,
        )

    @staticmethod
    def _jev_fallback_reason(decision) -> str:
        if decision.error:
            return decision.error
        if not decision.accepted:
            return "low_confidence"
        return "unknown"

    async def _run_jev_shadow(
        self,
        content: str,
        legacy_route: str,
    ) -> None:
        router = getattr(self, "jev_router", None)
        if router is None or not router.is_configured:
            return

        decision = await router.route(content)
        legacy_normalized = self._normalize_legacy_route_for_jev(
            legacy_route
        )

        logger.info(
            "JEV shadow | source=legacy | legacy=%s | jev=%s | "
            "confidence=%.4f | accepted=%s | match=%s | latency_ms=%s | "
            "error=%s",
            legacy_normalized,
            decision.route,
            decision.confidence,
            decision.accepted,
            decision.route == legacy_normalized,
            decision.latency_ms,
            decision.error,
        )

    def _schedule_jev_shadow(
        self,
        content: str,
        legacy_route: str,
    ) -> None:
        router = getattr(self, "jev_router", None)
        if router is None or not router.is_configured:
            return

        task = asyncio.create_task(
            self._run_jev_shadow(content, legacy_route)
        )
        tasks = getattr(self, "_jev_shadow_tasks", None)
        if tasks is None:
            tasks = set()
            self._jev_shadow_tasks = tasks
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def _select_production_route(
        self,
        content: str,
        legacy_model: str,
        legacy_effort: str,
        legacy_route: str,
    ) -> tuple[str, str, str]:
        """Select routing by mode and fail safely to the legacy router."""
        router = getattr(self, "jev_router", None)
        legacy_normalized = self._normalize_legacy_route_for_jev(
            legacy_route
        )

        if router is None:
            logger.info(
                "JEV routing | mode=legacy | source=legacy | "
                "fallback_reason=router_unavailable | legacy=%s",
                legacy_normalized,
            )
            return legacy_model, legacy_effort, legacy_route

        mode = getattr(router, "mode", "production")

        if mode == "legacy":
            logger.info(
                "JEV routing | mode=legacy | source=legacy | legacy=%s",
                legacy_normalized,
            )
            return legacy_model, legacy_effort, legacy_route

        if mode == "shadow":
            self._schedule_jev_shadow(content, legacy_route)
            logger.info(
                "JEV routing | mode=shadow | source=legacy | legacy=%s",
                legacy_normalized,
            )
            return legacy_model, legacy_effort, legacy_route

        if not router.is_configured:
            logger.info(
                "JEV production fallback | mode=production | source=legacy | "
                "fallback_reason=not_configured | legacy=%s",
                legacy_normalized,
            )
            return legacy_model, legacy_effort, legacy_route

        decision = await router.route(content)

        if not decision.accepted or decision.route is None:
            fallback_reason = self._jev_fallback_reason(decision)
            logger.info(
                "JEV production fallback | mode=production | source=legacy | "
                "fallback_reason=%s | legacy=%s | jev=%s | "
                "confidence=%.4f | latency_ms=%s | error=%s",
                fallback_reason,
                legacy_normalized,
                decision.route,
                decision.confidence,
                decision.latency_ms,
                decision.error,
            )
            return legacy_model, legacy_effort, legacy_route

        model, effort = self._route_config(decision.route)
        logger.info(
            "JEV production | mode=production | source=jev | legacy=%s | "
            "jev=%s | confidence=%.4f | latency_ms=%s | model=%s | effort=%s",
            legacy_normalized,
            decision.route,
            decision.confidence,
            decision.latency_ms,
            model,
            effort,
        )
        return model, effort, decision.route

    @staticmethod
    def select_chat_max_tokens(
        route: str
    ) -> int:

        if route == "deep-reasoning":
            return Config.DEEP_REASONING_MAX_TOKENS

        if route in {
            "regulation",
            "reasoning",
            "long-question",
        }:
            return Config.REASONING_MAX_TOKENS

        return Config.NORMAL_CHAT_MAX_TOKENS

    # ==========================================================================
    # Responses API
    # ==========================================================================

    async def call_gpt(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        history=None,
        reasoning_effort: str = "low"
    ) -> str:

        input_messages = []

        # ======================================================================
        # System
        # ======================================================================

        input_messages.append(
            {
                "role": "system",
                "content": system,
            }
        )

        # ======================================================================
        # History
        # ======================================================================

        if history:

            for item in history:

                role = item.get(
                    "role"
                )

                content = item.get(
                    "content",
                    ""
                )

                if (
                    role
                    not in {
                        "user",
                        "assistant",
                    }
                    or not content
                ):

                    continue

                input_messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        # ======================================================================
        # Current User
        # ======================================================================

        input_messages.append(
            {
                "role": "user",
                "content": user,
            }
        )

        try:

            response = await asyncio.wait_for(
                self.client.responses.create(
                    model=model,
                    input=input_messages,
                    reasoning={
                        "effort": reasoning_effort,
                    },
                    max_output_tokens=max_tokens,
                ),
                timeout=90
            )

            text = (
                response.output_text
                if response.output_text
                else ""
            ).strip()

            status = getattr(
                response,
                "status",
                None
            )
            incomplete_details = getattr(
                response,
                "incomplete_details",
                None
            )
            incomplete_reason = getattr(
                incomplete_details,
                "reason",
                None
            )

            if status == "incomplete":
                logger.warning(
                    "AI response incomplete | "
                    f"model={model} | "
                    f"effort={reasoning_effort} | "
                    f"reason={incomplete_reason} | "
                    f"max_output_tokens={max_tokens}"
                )

                if incomplete_reason == "max_output_tokens":
                    if text:
                        return (
                            f"{text}\n\n"
                            f"{Config.INCOMPLETE_OUTPUT_MSG}"
                        )
                    return Config.INCOMPLETE_OUTPUT_MSG

            return text

        except asyncio.TimeoutError:

            logger.warning(
                "OpenAI timeout | "
                f"model={model} | "
                f"effort={reasoning_effort}"
            )

            return Config.TIMEOUT_MSG

        except Exception as e:

            logger.exception(
                "OpenAI API error | "
                f"model={model} | "
                f"effort={reasoning_effort} | "
                f"error={e}"
            )

            return Config.ERROR_MSG

    # ==========================================================================
    # Chat
    # ==========================================================================

    async def chat(
        self,
        user_name: str,
        content: str,
        history=None
    ):

        (
            legacy_model,
            legacy_effort,
            legacy_route
        ) = self.select_chat_model(
            content
        )

        (
            model,
            reasoning_effort,
            route
        ) = await self._select_production_route(
            content,
            legacy_model,
            legacy_effort,
            legacy_route,
        )

        regulation_mode = any(
            keyword in content
            for keyword
            in Config.REGULATION_KEYWORDS
        )

        system_prompt = (
            self.get_system_prompt(
                regulation_mode=regulation_mode
            )
        )

        user_prompt = (
            f"ユーザー名: {user_name}\n"
            f"発言:\n{content}"
        )

        max_tokens = self.select_chat_max_tokens(
            route
        )

        logger.info(
            "AI route selected | "
            f"route={route} | "
            f"model={model} | "
            f"effort={reasoning_effort} | "
            f"max_output_tokens={max_tokens} | "
            f"history="
            f"{len(history) if history else 0}"
        )

        reply = await self.call_gpt(
            system=system_prompt,
            user=user_prompt,
            model=model,
            max_tokens=max_tokens,
            history=history,
            reasoning_effort=reasoning_effort
        )

        return (
            reply,
            model,
            route
        )

    # ==========================================================================
    # Translate
    # ==========================================================================

    async def translate(
        self,
        text: str,
        target_language: str
    ) -> str:

        system = """
あなたは高品質な翻訳AIです。

翻訳のみを行ってください。
原文の意味・ニュアンス・口調を可能な限り維持してください。
余計な解説は不要です。
""".strip()

        user = (
            f"次の文章を "
            f"{target_language} "
            f"へ翻訳してください。\n\n"
            f"{text}"
        )

        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.FAST_MODEL,
            max_tokens=1500,
            reasoning_effort=(
                Config.FAST_REASONING_EFFORT
            )
        )

    # ==========================================================================
    # Define Word
    # ==========================================================================

    async def define_word(
        self,
        word: str,
        wiki_mode: bool = False
    ) -> str:

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

        return await self.call_gpt(
            system=system,
            user=word,
            model=Config.FAST_MODEL,
            max_tokens=1000,
            reasoning_effort=(
                Config.FAST_REASONING_EFFORT
            )
        )

    # ==========================================================================
    # Summarize
    # ==========================================================================

    async def summarize(
        self,
        messages
    ) -> str:

        joined = "\n".join(
            f"- {message}"
            for message in messages
        )

        system = """
あなたは会話要約AIです。

入力された発言を読み、
重要な内容を短く分かりやすくまとめてください。

本人がどんな話題について何を話していたかが
分かる要約にしてください。
""".strip()

        user = (
            "以下の発言を要約してください。\n\n"
            f"{joined}"
        )

        return await self.call_gpt(
            system=system,
            user=user,
            model=Config.CHAT_MODEL,
            max_tokens=1000,
            reasoning_effort=(
                Config.CHAT_REASONING_EFFORT
            )
        )
