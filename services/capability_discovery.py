from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from services.capability_core import CapabilityRisk, CapabilitySpec
from services.write_intent_discovery import discover_write_intent


ACTION_VERBS = (
    "見たい", "確認", "表示", "見せて", "知りたい", "占いたい",
    "して", "してほしい", "使いたい", "調べたい", "変更", "変えて",
    "設定", "削除", "消して", "忘れて", "登録", "作って", "作成",
    "追加", "開始", "検索", "探して", "問い合わせたい", "相談したい",
    "連絡したい", "聞きたい",
)

CAPABILITY_MARKERS = (
    "ランキング", "順位", "レベル", "xp", "プロフィール", "実績", "運勢",
    "占い", "称号", "メモリー", "記憶", "履歴", "リマインダー", "翻訳",
    "要約", "辞書", "イベント", "予定", "投票", "アンケート", "検索",
    "メッセージ", "問い合わせ", "チケット", "管理人", "管理者", "運営",
    "サポート", "相談", "rank", "level", "profile", "achievement", "fortune",
    "title", "memory", "remind", "reminder", "translate", "summary", "define",
    "event", "poll", "search", "ticket", "support",
)

CHAT_INTENT_MARKERS = (
    "どう思う", "なぜ", "なんで", "理由", "分析", "比較して", "意味",
    "とは", "について", "教えて",
)


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    capability_id: str
    name: str
    description: str
    slash_command: str | None
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryDecision:
    should_route: bool
    candidates: tuple[DiscoveryCandidate, ...]
    reason: str


def should_attempt_discovery(content: str) -> bool:
    text = (content or "").strip().lower()
    if not text or len(text) > 180:
        return False
    if any(marker in text for marker in CHAT_INTENT_MARKERS):
        return False
    return (
        any(marker in text for marker in CAPABILITY_MARKERS)
        and any(marker in text for marker in ACTION_VERBS)
    )


def shortlist_capabilities(
    content: str,
    specs: Iterable[CapabilitySpec],
    *,
    limit: int = 4,
) -> tuple[DiscoveryCandidate, ...]:
    text = (content or "").strip().lower()
    ranked: list[DiscoveryCandidate] = []
    write_intent = discover_write_intent(text)

    aliases = {
        "level": ("レベル",),
        "leaderboard": ("レベルランキング",),
        "achievements": ("実績",),
        "fortune": ("運勢", "占い"),
        "profile": ("プロフィール",),
        "titles": ("称号",),
        "title_set": ("称号", "称号変更"),
        "memory_status": ("メモリー", "記憶", "履歴"),
        "memory_forget": ("メモリー", "記憶", "履歴", "履歴削除"),
        "remind": ("リマインダー", "reminder", "remind"),
        "translate": ("翻訳",),
        "summary": ("要約",),
        "define": ("辞書",),
        "message_search": ("検索", "メッセージ検索", "search"),
        "event_create": ("イベント", "イベント作成", "event"),
        "poll_create": ("投票", "アンケート", "poll"),
        "ticket_create": (
            "問い合わせ", "問い合わせチケット", "チケット", "管理人", "管理者",
            "運営", "サポート", "相談", "ticket", "support",
        ),
    }

    for spec in specs:
        if not spec.discoverable:
            continue

        if spec.risk is CapabilityRisk.WRITE_CONFIRM and (
            not write_intent.should_route
            or write_intent.capability_id != spec.capability_id
        ):
            continue

        terms = tuple(
            dict.fromkeys(
                term.strip().lower()
                for term in (spec.capability_id, spec.name, *spec.tags)
                if term and term.strip()
            )
        )
        matched = tuple(term for term in terms if term in text)
        semantic_matches = [
            alias
            for alias in aliases.get(spec.capability_id, ())
            if alias in text
        ]
        if spec.capability_id == "rankings" and (
            "ランキング" in text or "順位" in text
        ):
            semantic_matches.append("ランキング")
        matched = tuple(dict.fromkeys((*matched, *semantic_matches)))
        if not matched:
            continue

        score = sum(
            3.0 if term == spec.capability_id else 2.0
            for term in matched
        )
        if spec.name.lower() in text:
            score += 2.0
        if spec.capability_id == "weekly" and (
            "今週" in text or "週間" in text
        ):
            score += 3.0
        if spec.capability_id == "leaderboard" and "レベル" in text:
            score += 2.0
        if spec.capability_id == "message_search" and (
            "検索" in text or "探して" in text
        ):
            score += 3.0
        if spec.capability_id == "ticket_create" and any(
            marker in text
            for marker in ("問い合わせたい", "相談したい", "連絡したい", "チケット")
        ):
            score += 4.0
        if (
            write_intent.should_route
            and write_intent.capability_id == spec.capability_id
        ):
            score += 8.0

        ranked.append(
            DiscoveryCandidate(
                capability_id=spec.capability_id,
                name=spec.name,
                description=spec.description,
                slash_command=spec.slash_command,
                score=score,
                matched_terms=matched,
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.capability_id))
    return tuple(ranked[:limit])


def discover_locally(
    content: str,
    specs: Iterable[CapabilitySpec],
    *,
    limit: int = 4,
) -> DiscoveryDecision:
    if not should_attempt_discovery(content):
        return DiscoveryDecision(False, (), "gate_rejected")

    candidates = shortlist_capabilities(content, specs, limit=limit)
    if not candidates:
        return DiscoveryDecision(False, (), "no_local_candidate")

    return DiscoveryDecision(True, candidates, "local_candidate")
