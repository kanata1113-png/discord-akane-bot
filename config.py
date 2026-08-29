import os
import pytz

from dotenv import load_dotenv


# ==============================================================================
# Environment
# ==============================================================================

load_dotenv()


JST = pytz.timezone(
    "Asia/Tokyo"
)


class Config:

    # ==========================================================================
    # Discord / OpenAI
    # ==========================================================================

    DISCORD_TOKEN = os.getenv(
        "DISCORD_TOKEN"
    )

    OPENAI_API_KEY = os.getenv(
        "OPENAI_API_KEY"
    )

    # ==========================================================================
    # AI Models
    # ==========================================================================

    CHAT_MODEL = "gpt-5-mini"

    REASONING_MODEL = "gpt-5.1"

    FAST_MODEL = "gpt-4o"

    GPT_MODEL = CHAT_MODEL

    NORMAL_CHAT_MAX_TOKENS = 1500

    DAILY_LIMIT = 100

    # ==========================================================================
    # AI Memory
    # ==========================================================================

    MEMORY_MESSAGE_LIMIT = 12

    MEMORY_RETENTION_DAYS = 30

    # ==========================================================================
    # Level / XP
    # ==========================================================================

    XP_PER_MESSAGE = 10

    XP_COOLDOWN_SECONDS = 60

    # ==========================================================================
    # V31 Spam Protection
    # ==========================================================================

    SPAM_WINDOW_SECONDS = 5

    SPAM_MESSAGE_THRESHOLD = 5

    SPAM_STRIKE_RESET_SECONDS = 1800

    SPAM_TIMEOUT_1_SECONDS = 30

    SPAM_TIMEOUT_2_SECONDS = 300

    SPAM_TIMEOUT_3_SECONDS = 1800

    DUPLICATE_MESSAGE_THRESHOLD = 4

    MASS_MENTION_THRESHOLD = 8

    # ==========================================================================
    # V31 Ticket
    # ==========================================================================

    TICKET_TRANSCRIPT_LIMIT = 1000

    TICKET_CLOSE_CONFIRM_TIMEOUT = 60

    # ==========================================================================
    # V32 Profile / Achievement
    # ==========================================================================

    ACHIEVEMENT_NOTIFICATIONS = True

    PROFILE_ACHIEVEMENT_PREVIEW = 5

    TITLES = {
        "newcomer": {
            "name": "🌱 新入り",
            "description": "茜ちゃんのコミュニティへようこそ",
        },

        "regular": {
            "name": "💬 常連さん",
            "description": "100メッセージ達成",
        },

        "talkative": {
            "name": "🗣️ おしゃべり好き",
            "description": "500メッセージ達成",
        },

        "veteran": {
            "name": "🏅 ベテラン",
            "description": "1000メッセージ達成",
        },

        "level5": {
            "name": "⭐ 駆け出し",
            "description": "レベル5達成",
        },

        "level10": {
            "name": "🌟 熟練者",
            "description": "レベル10達成",
        },

        "level20": {
            "name": "👑 古参",
            "description": "レベル20達成",
        },

        "ai_friend": {
            "name": "🤖 茜の話し相手",
            "description": "AI会話10回達成",
        },

        "ai_partner": {
            "name": "🧠 茜の相棒",
            "description": "AI会話100回達成",
        },

        "supporter": {
            "name": "📩 相談者",
            "description": "Ticketを利用した",
        },

        "lucky": {
            "name": "🍀 運試し好き",
            "description": "今日の運勢を10回引いた",
        },
    }

    ACHIEVEMENTS = {
        "first_message": {
            "name": "はじめの一歩",
            "emoji": "🌱",
            "description": "初めてメッセージを送信",
        },

        "messages_100": {
            "name": "おしゃべり開始",
            "emoji": "💬",
            "description": "100メッセージ送信",
        },

        "messages_500": {
            "name": "チャット常連",
            "emoji": "🗣️",
            "description": "500メッセージ送信",
        },

        "messages_1000": {
            "name": "千の言葉",
            "emoji": "🏅",
            "description": "1000メッセージ送信",
        },

        "level_5": {
            "name": "Lv.5到達",
            "emoji": "⭐",
            "description": "レベル5に到達",
        },

        "level_10": {
            "name": "Lv.10到達",
            "emoji": "🌟",
            "description": "レベル10に到達",
        },

        "level_20": {
            "name": "Lv.20到達",
            "emoji": "👑",
            "description": "レベル20に到達",
        },

        "ai_10": {
            "name": "茜と雑談",
            "emoji": "🤖",
            "description": "茜とAI会話を10回",
        },

        "ai_100": {
            "name": "茜の相棒",
            "emoji": "🧠",
            "description": "茜とAI会話を100回",
        },

        "fortune_1": {
            "name": "今日の運勢",
            "emoji": "🔮",
            "description": "初めて今日の運勢を確認",
        },

        "fortune_10": {
            "name": "運試しの達人",
            "emoji": "🍀",
            "description": "10日分の運勢を確認",
        },

        "ticket_1": {
            "name": "相談してみた",
            "emoji": "📩",
            "description": "初めてTicketを利用",
        },
    }

    # ==========================================================================
    # V33 Ranking
    # ==========================================================================

    RANKING_LIMIT = 10

    # プロフィールに週間順位を表示
    SHOW_WEEKLY_RANK_IN_PROFILE = True

    # ==========================================================================
    # Database
    # ==========================================================================

    DB_NAME = (
        "/data/akane_v26.db"
        if os.path.exists("/data")
        else "akane_v26.db"
    )

    # ==========================================================================
    # AI Messages
    # ==========================================================================

    TIMEOUT_MSG = (
        "せっかく話しかけてもらったんやけど、"
        "君の質問に答えようと思うと"
        "ちょっと時間がかかりそうやわ。"
        "よかったらもう少し茜が答えやすいよう"
        "もっかいやり直してもろてええか？ "
        "頼むわ🙏✨"
    )

    ERROR_MSG = (
        "ごめん、ちょっと調子悪いみたいで"
        "うまく答えられへんかったわ... "
        "(エラー発生)"
    )

    EMPTY_MSG = (
        "（...言葉が見つからへんみたいや。"
        "もう一回試してみて？）"
    )

    # ==========================================================================
    # Regulation Keywords
    # ==========================================================================

    REGULATION_KEYWORDS = [
        "表現規制",
        "規制",
        "検閲",
        "制限",
        "禁止",
        "表現の自由",
        "言論統制",
        "弾圧",
        "ポリコレ",
    ]

    # ==========================================================================
    # Reasoning Keywords
    # ==========================================================================

    REASONING_KEYWORDS = [
        "法律",
        "憲法",
        "判例",
        "法的",
        "制度",
        "政策",
        "分析",
        "考察",
        "比較",
        "論点",
        "根拠",
        "反論",
        "メリット",
        "デメリット",
        "歴史的",
        "詳しく分析",
        "深く考えて",
    ]

    # ==========================================================================
    # Translation Reactions
    # ==========================================================================

    FLAG_MAP = {
        "🇺🇸": "English",
        "🇬🇧": "English",
        "🇨🇦": "English",
        "🇦🇺": "English",

        "🇯🇵": "Japanese",
        "🇨🇳": "Chinese",
        "🇰🇷": "Korean",

        "🇫🇷": "French",
        "🇩🇪": "German",
        "🇮🇹": "Italian",
        "🇪🇸": "Spanish",

        "🇷🇺": "Russian",
        "🇻🇳": "Vietnamese",
        "🇹🇭": "Thai",
        "🇮🇩": "Indonesian",
    }
