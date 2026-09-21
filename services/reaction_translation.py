from __future__ import annotations

import hashlib
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone

from config import Config
from services.capability_core import CapabilityRisk, CapabilitySpec


REACTION_TRANSLATE_CAPABILITY_ID = "reaction_translate"

REACTION_TRANSLATE_SPEC = CapabilitySpec(
    capability_id=REACTION_TRANSLATE_CAPABILITY_ID,
    name="リアクション翻訳",
    description="国旗リアクションで既存メッセージを対応言語へ翻訳する",
    risk=CapabilityRisk.READ_ONLY,
    category="ai_event",
    slash_command=None,
    discoverable=False,
    incurs_external_cost=True,
    tags=("reaction", "flag", "translate", "translation", "翻訳", "国旗"),
)


@dataclass(frozen=True, slots=True)
class TranslationCacheKey:
    source_hash: str
    language: str


class ReactionTranslationService:
    """Event-triggered reaction translation with local cache and rate limiting.

    Jev is deliberately not part of this path: the flag deterministically fixes
    the target language, so the cheapest safe path is local validation followed
    by the existing Luna-backed translation service.
    """

    def __init__(self, bot):
        self.bot = bot
        self._cache: OrderedDict[TranslationCacheKey, str] = OrderedDict()
        self._user_requests: dict[int, deque[float]] = defaultdict(deque)
        self.card_ids: dict[tuple[int, str], int] = {}
        self.card_source_hashes: dict[tuple[int, str], str] = {}

    @staticmethod
    def language_for_flag(emoji: str) -> str | None:
        return Config.FLAG_MAP.get(emoji)

    @staticmethod
    def source_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def preview(text: str, limit: int | None = None) -> str:
        max_chars = limit or Config.REACTION_TRANSLATION_PREVIEW_CHARS
        normalized = " ".join((text or "").split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max(1, max_chars - 1)].rstrip() + "…"

    def allow_user(self, user_id: int, now: float | None = None) -> bool:
        current = now if now is not None else datetime.now(timezone.utc).timestamp()
        window = float(Config.REACTION_TRANSLATION_RATE_WINDOW_SECONDS)
        limit = int(Config.REACTION_TRANSLATION_RATE_LIMIT)
        queue = self._user_requests[user_id]
        while queue and current - queue[0] >= window:
            queue.popleft()
        if len(queue) >= limit:
            return False
        queue.append(current)
        return True

    async def translate(self, text: str, language: str) -> str:
        key = TranslationCacheKey(self.source_hash(text), language)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        translated = await self.bot.ai.translate(text, language)
        if not translated or not translated.strip():
            translated = Config.ERROR_MSG

        self._cache[key] = translated
        self._cache.move_to_end(key)
        while len(self._cache) > Config.REACTION_TRANSLATION_CACHE_SIZE:
            self._cache.popitem(last=False)
        return translated

    def remember_card(
        self,
        *,
        source_message_id: int,
        language: str,
        card_message_id: int,
        source_text: str,
    ) -> None:
        key = (source_message_id, language)
        self.card_ids[key] = card_message_id
        self.card_source_hashes[key] = self.source_hash(source_text)

    def card_is_current(self, source_message_id: int, language: str, source_text: str) -> bool:
        key = (source_message_id, language)
        return (
            key in self.card_ids
            and self.card_source_hashes.get(key) == self.source_hash(source_text)
        )
