from types import SimpleNamespace

from cogs.admin import AdminCommands
from cogs.general import GeneralCog


GENERAL_COMMANDS = {
    "translate": "AI翻訳",
    "define": "AI辞書",
    "summary": "自分の発言要約",
    "event": "イベント作成",
    "poll": "投票作成",
    "search": "メッセージ検索",
    "level": "レベル確認",
    "leaderboard": "レベルランキング TOP30",
    "remind": "リマインダー",
    "memory": "茜が覚えている会話履歴を確認",
    "forget": "自分のAI会話履歴を削除",
    "profile": "プロフィールを表示",
    "fortune": "今日の運勢を占う",
    "achievements": "実績一覧を表示",
    "titles": "獲得済み称号を表示",
    "title_set": "プロフィールの称号を変更",
    "weekly": "今週のXPランキング",
    "rankings": "サーバー内ランキング",
}

ADMIN_COMMANDS = {
    "status": "現在の茜Botサーバー設定を確認",
    "config_log": "監査ログ設定",
    "config_welcome": "挨拶設定",
    "config_starboard": "殿堂入り設定",
    "config_autochat": "常駐チャット設定",
    "config_monthly": "月次ルール通知設定",
    "setup_ticket": "Ticketパネル設置",
    "rolepanel": "ロールパネル作成",
    "level_reward": "レベル報酬設定",
    "level_reward_remove": "レベル報酬削除",
    "level_reward_list": "レベル報酬一覧",
    "filter_add": "NGワード追加",
    "response_add": "自動応答追加",
    "kick": "メンバーをKick",
    "ban": "メンバーをBan",
    "purge": "メッセージ削除",
}


def command_metadata(commands):
    return {command.name: command.description for command in commands}


def test_general_command_names_and_descriptions_are_stable():
    cog = GeneralCog(SimpleNamespace())
    assert command_metadata(cog.get_app_commands()) == GENERAL_COMMANDS


def test_admin_group_name_description_and_children_are_stable():
    group = AdminCommands(SimpleNamespace())

    assert group.name == "admin"
    assert group.description == "サーバー管理コマンド"
    assert command_metadata(group.commands) == ADMIN_COMMANDS
