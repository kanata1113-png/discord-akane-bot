from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WriteIntentDecision:
    should_route: bool
    capability_id: str | None = None
    name: str | None = None
    reason: str = "no_write_intent"


_TITLE_SUBJECTS = ("称号", "title")
_TITLE_WRITES = ("変更", "変えて", "設定", "装備", "つけて")
_MEMORY_SUBJECTS = ("メモリー", "記憶", "履歴", "memory")
_MEMORY_DELETES = ("消して", "削除", "忘れて", "忘れ", "clear", "delete", "forget")
_REMINDER_SUBJECTS = ("リマインダー", "reminder", "remind")
_REMINDER_ACTIONS = ("登録", "設定", "作って", "追加", "お願い", "して", "したい")
_EVENT_SUBJECTS = ("イベント", "event", "予定")
_EVENT_ACTIONS = ("作って", "作成", "登録", "設定", "追加", "開いて")
_POLL_SUBJECTS = ("投票", "アンケート", "poll")
_POLL_ACTIONS = ("作って", "作成", "開始", "登録", "追加", "取りたい")
_TICKET_SUBJECTS = (
    "チケット", "ticket", "問い合わせ", "管理人", "管理者", "運営", "サポート", "相談"
)
_TICKET_ACTIONS = (
    "作って", "作成", "開いて", "問い合わせたい", "相談したい", "連絡したい",
    "聞きたい", "送りたい", "したい", "お願い",
)


def discover_write_intent(content: str) -> WriteIntentDecision:
    """Detect approved WRITE_CONFIRM intents locally without executing them."""

    text = (content or "").strip().lower()
    if not text or len(text) > 180:
        return WriteIntentDecision(False, reason="gate_rejected")

    if any(subject in text for subject in _TITLE_SUBJECTS) and any(
        verb in text for verb in _TITLE_WRITES
    ):
        return WriteIntentDecision(True, "title_set", "称号変更", "title_write")

    if any(subject in text for subject in _MEMORY_SUBJECTS) and any(
        verb in text for verb in _MEMORY_DELETES
    ):
        return WriteIntentDecision(
            True,
            "memory_forget",
            "会話履歴削除",
            "memory_delete",
        )

    if any(subject in text for subject in _REMINDER_SUBJECTS) and any(
        verb in text for verb in _REMINDER_ACTIONS
    ):
        return WriteIntentDecision(
            True,
            "remind",
            "リマインダー登録",
            "reminder_write",
        )

    if any(subject in text for subject in _EVENT_SUBJECTS) and any(
        verb in text for verb in _EVENT_ACTIONS
    ):
        return WriteIntentDecision(
            True,
            "event_create",
            "イベント作成",
            "event_create",
        )

    if any(subject in text for subject in _POLL_SUBJECTS) and any(
        verb in text for verb in _POLL_ACTIONS
    ):
        return WriteIntentDecision(
            True,
            "poll_create",
            "投票作成",
            "poll_create",
        )

    if any(subject in text for subject in _TICKET_SUBJECTS) and any(
        verb in text for verb in _TICKET_ACTIONS
    ):
        return WriteIntentDecision(
            True,
            "ticket_create",
            "問い合わせTicket作成",
            "ticket_create",
        )

    return WriteIntentDecision(False)
