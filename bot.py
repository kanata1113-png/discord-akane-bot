import discord
from discord import app_commands
from discord.ext import commands, tasks

import openai
from openai import OpenAI

import os
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta, time
import pytz
import re
import io

from collections import defaultdict, deque
from typing import Optional, List
from dotenv import load_dotenv


# ==============================================================================
# 0. 初期設定
# ==============================================================================

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AkaneBot")


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

JST = pytz.timezone("Asia/Tokyo")


class Config:

    # --------------------------------------------------------------------------
    # AI
    # --------------------------------------------------------------------------

    GPT_MODEL = "gpt-5-mini"
    FAST_MODEL = "gpt-4o"

    NORMAL_CHAT_MAX_TOKENS = 1500

    # --------------------------------------------------------------------------
    # Database
    # --------------------------------------------------------------------------

    # Railway Volume を /data に設定している場合はこちらを使用
    DB_NAME = (
        "/data/akane_v26.db"
        if os.path.exists("/data")
        else "akane_v26.db"
    )

    # --------------------------------------------------------------------------
    # 利用制限
    # --------------------------------------------------------------------------

    DAILY_LIMIT = 100

    # --------------------------------------------------------------------------
    # 定型文
    # --------------------------------------------------------------------------

    TIMEOUT_MSG = (
        "せっかく話しかけてもらったんやけど、"
        "君の質問に答えようと思うとちょっと時間がかかりそうやわ。"
        "よかったらもう少し茜が答えやすいようにもっかいやり直してもろてええか？ "
        "頼むわ🙏✨"
    )

    ERROR_MSG = (
        "ごめん、ちょっと調子悪いみたいで"
        "うまく答えられへんかったわ... (エラー発生)"
    )

    EMPTY_MSG = (
        "（...言葉が見つからへんみたいや。"
        "もう一回試してみて？）"
    )

    # --------------------------------------------------------------------------
    # 表現規制関連
    # --------------------------------------------------------------------------

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

    # --------------------------------------------------------------------------
    # 翻訳リアクション
    # --------------------------------------------------------------------------

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


# ==============================================================================
# OpenAI Client
# ==============================================================================

if OPENAI_API_KEY:

    openai_client = openai.OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=60.0
    )

else:

    openai_client = None

    logger.warning(
        "OpenAI API Key is missing."
    )


# ==============================================================================
# 1. Database Manager
# ==============================================================================


class DatabaseManager:

    def __init__(self, db_path):

        self.path = db_path


    # --------------------------------------------------------------------------
    # DB初期化
    # --------------------------------------------------------------------------

    async def init(self):

        async with aiosqlite.connect(self.path) as db:

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_log (
                    user_id TEXT,
                    date TEXT,
                    count INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS starboard_log (
                    message_id INTEGER PRIMARY KEY
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    welcome_ch INTEGER,
                    log_ch INTEGER,
                    starboard_ch INTEGER,
                    auto_chat_ch INTEGER
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS level_rewards (
                    guild_id INTEGER,
                    level INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY(guild_id, level)
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reaction_roles (
                    message_id INTEGER,
                    emoji TEXT,
                    role_id INTEGER
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS ng_words (
                    guild_id INTEGER,
                    word TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS auto_replies (
                    guild_id INTEGER,
                    trigger TEXT,
                    response TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    message TEXT,
                    end_time TEXT
                )
                """
            )

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_rules (
                    guild_id INTEGER PRIMARY KEY,
                    rule_ch INTEGER,
                    target_ch INTEGER
                )
                """
            )

            await db.commit()


        logger.info(
            f"Database initialized: {self.path}"
        )


    # --------------------------------------------------------------------------
    # DB Helper
    # --------------------------------------------------------------------------

    async def _execute(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(self.path) as db:

            await db.execute(
                query,
                params
            )

            await db.commit()


    async def _fetchone(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(self.path) as db:

            cursor = await db.execute(
                query,
                params
            )

            return await cursor.fetchone()


    async def _fetchall(
        self,
        query,
        params=()
    ):

        async with aiosqlite.connect(self.path) as db:

            cursor = await db.execute(
                query,
                params
            )

            return await cursor.fetchall()


    # --------------------------------------------------------------------------
    # Guild Config
    # --------------------------------------------------------------------------

    async def set_config(
        self,
        guild_id: int,
        col: str,
        val: int
    ):

        curr = await self._fetchone(
            "SELECT guild_id FROM guild_settings WHERE guild_id=?",
            (guild_id,)
        )

        if curr:

            await self._execute(
                f"""
                UPDATE guild_settings
                SET {col}=?
                WHERE guild_id=?
                """,
                (
                    val,
                    guild_id
                )
            )

        else:

            await self._execute(
                f"""
                INSERT INTO guild_settings
                (guild_id, {col})
                VALUES (?, ?)
                """,
                (
                    guild_id,
                    val
                )
            )


    async def get_config(
        self,
        guild_id: int,
        col: str
    ) -> Optional[int]:

        res = await self._fetchone(
            f"""
            SELECT {col}
            FROM guild_settings
            WHERE guild_id=?
            """,
            (guild_id,)
        )

        return res[0] if res else None


    # --------------------------------------------------------------------------
    # XP
    # --------------------------------------------------------------------------

    async def add_xp(
        self,
        user_id: int,
        amount: int = 10
    ) -> bool:

        row = await self._fetchone(
            """
            SELECT xp, level
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        if row:

            xp, level = row

            xp += amount

            is_up = False

            if xp >= level * 100:

                # v27では既存仕様を維持
                # XP方式の改善はv30で実施予定
                xp = 0

                level += 1

                is_up = True


            await self._execute(
                """
                UPDATE users
                SET xp=?, level=?
                WHERE user_id=?
                """,
                (
                    xp,
                    level,
                    user_id
                )
            )

            return is_up


        else:

            await self._execute(
                """
                INSERT INTO users
                (user_id, xp, level)
                VALUES (?, ?, ?)
                """,
                (
                    user_id,
                    amount,
                    1
                )
            )

            return False


    async def get_user_data(
        self,
        user_id: int
    ):

        res = await self._fetchone(
            """
            SELECT level, xp
            FROM users
            WHERE user_id=?
            """,
            (user_id,)
        )

        return res if res else (1, 0)


    async def get_leaderboard(
        self,
        limit=30
    ):

        return await self._fetchall(
            """
            SELECT user_id, level, xp
            FROM users
            ORDER BY level DESC, xp DESC
            LIMIT ?
            """,
            (limit,)
        )


    # --------------------------------------------------------------------------
    # Reminder
    # --------------------------------------------------------------------------

    async def add_reminder(
        self,
        user_id: int,
        channel_id: int,
        message: str,
        minutes: int
    ):

        if minutes <= 0:

            raise ValueError(
                "minutes must be greater than 0"
            )


        end_time = (
            datetime.now(JST)
            + timedelta(minutes=minutes)
        ).isoformat()


        await self._execute(
            """
            INSERT INTO reminders
            (
                user_id,
                channel_id,
                message,
                end_time
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                channel_id,
                message,
                end_time
            )
        )


    # --------------------------------------------------------------------------
    # Daily AI Limit
    # --------------------------------------------------------------------------

    async def check_daily_limit(
        self,
        user_id: str
    ) -> bool:

        today = datetime.now(
            JST
        ).strftime(
            "%Y-%m-%d"
        )


        row = await self._fetchone(
            """
            SELECT count
            FROM usage_log
            WHERE user_id=? AND date=?
            """,
            (
                user_id,
                today
            )
        )


        count = (
            row[0]
            if row
            else 0
        )


        if count >= Config.DAILY_LIMIT:

            return False


        if row:

            await self._execute(
                """
                UPDATE usage_log
                SET count=count+1
                WHERE user_id=? AND date=?
                """,
                (
                    user_id,
                    today
                )
            )

        else:

            await self._execute(
                """
                INSERT INTO usage_log
                (user_id, date, count)
                VALUES (?, ?, 1)
                """,
                (
                    user_id,
                    today
                )
            )


        return True


# ==============================================================================
# 2. AI Manager
# ==============================================================================


class AiManager:

    def __init__(self):

        self.model = Config.GPT_MODEL


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
            "gpt-5" in model
            or "o1" in model
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


            resp = await loop.run_in_executor(
                None,
                lambda: openai_client.chat.completions.create(
                    **params
                )
            )


            content = (
                resp
                .choices[0]
                .message
                .content
            )


            if (
                content is None
                or len(content.strip()) == 0
            ):

                return Config.EMPTY_MSG


            return content


        except Exception as e:

            logger.exception(
                f"AI Error: {e}"
            )


            if (
                "timed out"
                in str(e).lower()
            ):

                return Config.TIMEOUT_MSG


            return Config.ERROR_MSG


    # --------------------------------------------------------------------------
    # 茜チャット
    # --------------------------------------------------------------------------

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
                "親しみやすく、友達のような関西弁で振る舞ってください。"
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


    # --------------------------------------------------------------------------
    # 翻訳
    # --------------------------------------------------------------------------

    async def translate(
        self,
        text: str,
        target_lang: str
    ) -> str:


        return await self.call_gpt(

            f"""
            Translate to {target_lang}.
            Output ONLY the translated text.
            """,

            text,

            model=Config.FAST_MODEL
        )


    # --------------------------------------------------------------------------
    # 辞書
    # --------------------------------------------------------------------------

    async def define_word(
        self,
        word: str,
        wiki_mode: bool
    ) -> str:


        if wiki_mode:

            sys = (
                "あなたはWikipediaの要約アシスタントです。"
                f"「{word}」について、Wikipediaの記事内容のような"
                "客観的な事実に基づき、400文字以内で"
                "簡潔に要約してください。"
            )

        else:

            sys = (
                "あなたは高性能な辞書です。"
                f"「{word}」という言葉の意味を、"
                "400文字以内で分かりやすく解説してください。"
            )


        sys += (
            "\n【重要】必ず文章を完結させてください。"
            "途中で切れてはいけません。"
        )


        return await self.call_gpt(

            sys,

            word,

            model=Config.FAST_MODEL,

            max_tokens=1000
        )


    # --------------------------------------------------------------------------
    # 要約
    # --------------------------------------------------------------------------

    async def summarize(
        self,
        text_list: List[str]
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


# ==============================================================================
# 3. UI Views
# ==============================================================================


class EventView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    async def _update(
        self,
        interaction,
        status
    ):

        embed = (
            interaction
            .message
            .embeds[0]
        )


        new_fields = []


        target = (
            f"【{status}】"
        )


        for field in embed.fields:

            values = [

                line

                for line
                in field.value.split("\n")

                if (
                    interaction.user.mention
                    not in line
                    and "なし" not in line
                )
            ]


            if field.name == target:

                values.append(
                    f"• {interaction.user.mention}"
                )


            new_fields.append(

                (
                    field.name,

                    "\n".join(values)
                    or "なし"
                )
            )


        new_embed = discord.Embed(

            title=embed.title,

            description=embed.description,

            color=embed.color
        )


        if embed.footer.text:

            new_embed.set_footer(
                text=embed.footer.text
            )


        new_embed.timestamp = (
            embed.timestamp
        )


        for name, value in new_fields:

            new_embed.add_field(

                name=name,

                value=value
            )


        await interaction.response.edit_message(

            embed=new_embed
        )


    @discord.ui.button(

        label="参加",

        style=discord.ButtonStyle.success,

        custom_id="ev_join"
    )

    async def join(
        self,
        interaction,
        button
    ):

        await self._update(
            interaction,
            "参加"
        )


    @discord.ui.button(

        label="不参加",

        style=discord.ButtonStyle.danger,

        custom_id="ev_leave"
    )

    async def leave(
        self,
        interaction,
        button
    ):

        await self._update(
            interaction,
            "不参加"
        )


# ==============================================================================
# Ticket
# ==============================================================================


class TicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(

        label="問い合わせ",

        style=discord.ButtonStyle.primary,

        emoji="📩",

        custom_id="tk_open"
    )

    async def create(
        self,
        interaction,
        button
    ):


        try:

            overwrites = {

                interaction.guild.default_role:
                    discord.PermissionOverwrite(
                        read_messages=False
                    ),

                interaction.user:
                    discord.PermissionOverwrite(
                        read_messages=True
                    ),

                interaction.guild.me:
                    discord.PermissionOverwrite(
                        read_messages=True
                    )
            }


            channel = await interaction.guild.create_text_channel(

                f"ticket-{interaction.user.name}",

                overwrites=overwrites
            )


            await interaction.response.send_message(

                f"個室を作ったで！: {channel.mention}",

                ephemeral=True
            )


            await channel.send(

                f"{interaction.user.mention} ここで要件を聞くで。",

                view=TicketCloseView()
            )


        except discord.Forbidden:

            logger.warning(
                "Ticket creation permission denied."
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "チケットを作る権限が茜にないみたいや。",

                    ephemeral=True
                )


        except Exception as e:

            logger.exception(
                f"Ticket creation failed: {e}"
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "チケット作成中にエラーが起きたで。",

                    ephemeral=True
                )


# ==============================================================================
# Ticket Close
# ==============================================================================


class TicketCloseView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(

        label="解決・閉じる",

        style=discord.ButtonStyle.danger,

        custom_id="tk_close"
    )

    async def close(
        self,
        interaction,
        button
    ):


        try:

            await interaction.response.send_message(
                "ほな閉じるで〜"
            )


            await asyncio.sleep(3)


            await interaction.channel.delete()


        except discord.Forbidden:

            logger.warning(
                "Ticket channel delete permission denied."
            )


        except Exception as e:

            logger.exception(
                f"Ticket close failed: {e}"
            )


# ==============================================================================
# 4. Admin Command Group
# ==============================================================================


class AdminCommands(
    app_commands.Group
):

    def __init__(
        self,
        bot
    ):

        super().__init__(

            name="admin",

            description="サーバー管理コマンド"
        )

        self.bot = bot


    # --------------------------------------------------------------------------
    # ★ v27 管理者権限チェック
    # --------------------------------------------------------------------------

    async def interaction_check(
        self,
        interaction: discord.Interaction
    ) -> bool:


        if interaction.guild is None:

            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "このコマンドはサーバー内専用やで。",

                    ephemeral=True
                )

            return False


        if not interaction.user.guild_permissions.administrator:

            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "⛔ このコマンドは管理者専用やで！",

                    ephemeral=True
                )

            return False


        return True


    # --------------------------------------------------------------------------
    # Config Log
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="config_log",

        description="監査ログ設定"
    )

    async def config_log(

        self,

        interaction: discord.Interaction,

        channel: discord.TextChannel
    ):


        await self.bot.db.set_config(

            interaction.guild.id,

            "log_ch",

            channel.id
        )


        await interaction.response.send_message(

            f"ログ出力先: {channel.mention}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Welcome
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="config_welcome",

        description="挨拶設定"
    )

    async def config_welcome(

        self,

        interaction: discord.Interaction,

        channel: discord.TextChannel
    ):


        await self.bot.db.set_config(

            interaction.guild.id,

            "welcome_ch",

            channel.id
        )


        await interaction.response.send_message(

            f"挨拶場所: {channel.mention}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Starboard
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="config_starboard",

        description="殿堂入り設定"
    )

    async def config_starboard(

        self,

        interaction: discord.Interaction,

        channel: discord.TextChannel
    ):


        await self.bot.db.set_config(

            interaction.guild.id,

            "starboard_ch",

            channel.id
        )


        await interaction.response.send_message(

            f"殿堂入り先: {channel.mention}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Auto Chat
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="config_autochat",

        description="常駐チャット設定"
    )

    async def config_autochat(

        self,

        interaction: discord.Interaction,

        channel: discord.TextChannel
    ):


        await self.bot.db.set_config(

            interaction.guild.id,

            "auto_chat_ch",

            channel.id
        )


        await interaction.response.send_message(

            f"常駐場所: {channel.mention}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Monthly
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="config_monthly",

        description="月次ルール通知設定"
    )

    async def config_monthly(

        self,

        interaction: discord.Interaction,

        rule_ch: discord.TextChannel,

        target_ch: discord.TextChannel
    ):


        await self.bot.db._execute(

            """
            INSERT OR REPLACE INTO monthly_rules
            (
                guild_id,
                rule_ch,
                target_ch
            )
            VALUES (?, ?, ?)
            """,

            (
                interaction.guild.id,
                rule_ch.id,
                target_ch.id
            )
        )


        await interaction.response.send_message(

            "月次通知を設定したで。",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Ticket
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="setup_ticket",

        description="チケット設置"
    )

    async def setup_ticket(

        self,

        interaction: discord.Interaction
    ):


        try:

            await interaction.channel.send(

                "📩 サポート窓口",

                view=TicketView()
            )


            await interaction.response.send_message(

                "設置完了",

                ephemeral=True
            )


        except Exception as e:

            logger.exception(
                f"Ticket panel setup failed: {e}"
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "チケット設置中にエラーが起きたで。",

                    ephemeral=True
                )


    # --------------------------------------------------------------------------
    # Reaction Role
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="rolepanel",

        description="ロールパネル作成"
    )

    async def rolepanel(

        self,

        interaction: discord.Interaction,

        message_id: str,

        emoji: str,

        role: discord.Role
    ):


        try:

            msg = await interaction.channel.fetch_message(

                int(message_id)
            )


            await msg.add_reaction(
                emoji
            )


            await self.bot.db._execute(

                """
                INSERT INTO reaction_roles
                (
                    message_id,
                    emoji,
                    role_id
                )
                VALUES (?, ?, ?)
                """,

                (
                    msg.id,
                    emoji,
                    role.id
                )
            )


            await interaction.response.send_message(

                "✅ リアクションロールを設定したで。",

                ephemeral=True
            )


        except ValueError:

            await interaction.response.send_message(

                "メッセージIDは数字で指定してな！",

                ephemeral=True
            )


        except discord.NotFound:

            await interaction.response.send_message(

                "そのメッセージが見つからへんかったで。",

                ephemeral=True
            )


        except discord.Forbidden:

            await interaction.response.send_message(

                "茜に必要な権限がないみたいや。",

                ephemeral=True
            )


        except Exception as e:

            logger.exception(

                f"Role panel setup failed: {e}"
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "リアクションロール設定中にエラーが起きたで。",

                    ephemeral=True
                )


    # --------------------------------------------------------------------------
    # Level Reward
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="level_reward",

        description="レベル報酬設定"
    )

    @app_commands.describe(

        level="到達レベル",

        role="付与するロール"
    )

    async def level_reward(

        self,

        interaction: discord.Interaction,

        level: int,

        role: discord.Role
    ):


        await self.bot.db._execute(

            """
            INSERT OR REPLACE INTO level_rewards
            (
                guild_id,
                level,
                role_id
            )
            VALUES (?, ?, ?)
            """,

            (
                interaction.guild.id,
                level,
                role.id
            )
        )


        await interaction.response.send_message(

            f"Lv.{level} で {role.name} をあげる設定にしたで！",

            ephemeral=True
        )


    @app_commands.command(

        name="level_reward_remove",

        description="レベル報酬削除"
    )

    async def level_reward_remove(

        self,

        interaction: discord.Interaction,

        level: int
    ):


        await self.bot.db._execute(

            """
            DELETE FROM level_rewards
            WHERE guild_id=? AND level=?
            """,

            (
                interaction.guild.id,
                level
            )
        )


        await interaction.response.send_message(

            f"Lv.{level} の報酬設定を削除したで。",

            ephemeral=True
        )


    @app_commands.command(

        name="level_reward_list",

        description="レベル報酬一覧"
    )

    async def level_reward_list(

        self,

        interaction: discord.Interaction
    ):


        rows = await self.bot.db._fetchall(

            """
            SELECT level, role_id
            FROM level_rewards
            WHERE guild_id=?
            ORDER BY level ASC
            """,

            (
                interaction.guild.id,
            )
        )


        if not rows:

            await interaction.response.send_message(

                "設定なし。",

                ephemeral=True
            )

            return


        text = "\n".join(

            [
                f"Lv.{row[0]} -> <@&{row[1]}>"

                for row in rows
            ]
        )


        await interaction.response.send_message(

            embed=discord.Embed(

                title="レベル報酬一覧",

                description=text
            ),

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # NG Word
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="filter_add",

        description="NGワード追加"
    )

    async def filter_add(

        self,

        interaction: discord.Interaction,

        word: str
    ):


        await self.bot.db._execute(

            """
            INSERT INTO ng_words
            (
                guild_id,
                word
            )
            VALUES (?, ?)
            """,

            (
                interaction.guild.id,
                word
            )
        )


        await interaction.response.send_message(

            f"NG追加: {word}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Auto Reply
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="response_add",

        description="自動応答追加"
    )

    async def response_add(

        self,

        interaction: discord.Interaction,

        trigger: str,

        response: str
    ):


        await self.bot.db._execute(

            """
            INSERT INTO auto_replies
            (
                guild_id,
                trigger,
                response
            )
            VALUES (?, ?, ?)
            """,

            (
                interaction.guild.id,
                trigger,
                response
            )
        )


        await interaction.response.send_message(

            f"応答追加: {trigger} -> {response}",

            ephemeral=True
        )


    # --------------------------------------------------------------------------
    # Kick
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="kick",

        description="Kick"
    )

    async def kick(

        self,

        interaction: discord.Interaction,

        member: discord.Member
    ):


        try:

            await member.kick()


            await interaction.response.send_message(

                "Kick完了"
            )


        except discord.Forbidden:

            await interaction.response.send_message(

                "そのメンバーをKickする権限が茜にないみたいや。",

                ephemeral=True
            )


        except Exception as e:

            logger.exception(
                f"Kick failed: {e}"
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "Kick処理中にエラーが起きたで。",

                    ephemeral=True
                )


    # --------------------------------------------------------------------------
    # Ban
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="ban",

        description="Ban"
    )

    async def ban(

        self,

        interaction: discord.Interaction,

        member: discord.Member
    ):


        try:

            await member.ban()


            await interaction.response.send_message(

                "Ban完了"
            )


        except discord.Forbidden:

            await interaction.response.send_message(

                "そのメンバーをBanする権限が茜にないみたいや。",

                ephemeral=True
            )


        except Exception as e:

            logger.exception(
                f"Ban failed: {e}"
            )


            if not interaction.response.is_done():

                await interaction.response.send_message(

                    "Ban処理中にエラーが起きたで。",

                    ephemeral=True
                )


    # --------------------------------------------------------------------------
    # Purge
    # --------------------------------------------------------------------------

    @app_commands.command(

        name="purge",

        description="メッセージ削除"
    )

    @app_commands.describe(

        amount="削除数",

        user="対象ユーザー",

        hours="対象期間(時間)"
    )

    async def purge(

        self,

        interaction: discord.Interaction,

        amount: int,

        user: Optional[discord.Member] = None,

        hours: Optional[int] = None
    ):


        if amount < 1:

            await interaction.response.send_message(

                "削除数は1以上にしてな。",

                ephemeral=True
            )

            return


        await interaction.response.defer(
            ephemeral=True
        )


        cutoff = (

            datetime.now(pytz.utc)
            - timedelta(hours=hours)

            if hours

            else None
        )


        def check(message):

            if (
                user
                and message.author != user
            ):

                return False


            if (
                cutoff
                and message.created_at < cutoff
            ):

                return False


            return True


        try:

            deleted = await interaction.channel.purge(

                limit=min(amount, 300),

                check=check
            )


            await interaction.followup.send(

                f"{len(deleted)}件 削除したで。",

                ephemeral=True
            )


        except discord.Forbidden:

            await interaction.followup.send(

                "メッセージを削除する権限が茜にないみたいや。",

                ephemeral=True
            )


        except Exception as e:

            logger.exception(
                f"Purge failed: {e}"
            )


            await interaction.followup.send(

                "メッセージ削除中にエラーが起きたで。",

                ephemeral=True
            )


# ==============================================================================
# 5. Bot Main Class
# ==============================================================================


class AkaneBot(
    commands.Bot
):

    def __init__(self):

        intents = discord.Intents.all()


        super().__init__(

            command_prefix="!",

            intents=intents,

            help_command=None
        )


        self.db = DatabaseManager(
            Config.DB_NAME
        )


        self.ai = AiManager()


        self.spam_check = defaultdict(

            lambda: deque(
                maxlen=5
            )
        )


    # --------------------------------------------------------------------------
    # Setup
    # --------------------------------------------------------------------------

    async def setup_hook(self):


        await self.db.init()


        # Persistent View
        self.add_view(
            EventView()
        )

        self.add_view(
            TicketView()
        )

        self.add_view(
            TicketCloseView()
        )


        # Admin command
        self.tree.add_command(

            AdminCommands(self)
        )


        # Background Tasks
        self.loop_reminders.start()

        self.loop_monthly.start()


    # --------------------------------------------------------------------------
    # Ready
    # --------------------------------------------------------------------------

    async def on_ready(self):


        logger.info(
            f"Logged in as {self.user}"
        )


        logger.info(
            f"Discord.py version: {discord.__version__}"
        )


        logger.info(
            f"OpenAI version: {openai.__version__}"
        )


        logger.info(
            f"Database: {Config.DB_NAME}"
        )


        logger.info(
            f"Guild count: {len(self.guilds)}"
        )


        try:

            synced = await self.tree.sync()


            logger.info(
                f"Slash commands synced: {len(synced)}"
            )


        except Exception as e:

            logger.exception(
                f"Command sync failed: {e}"
            )


    # ==============================================================================
    # Background Tasks
    # ==============================================================================


    @tasks.loop(
        seconds=60
    )

    async def loop_reminders(self):


        try:

            now_str = datetime.now(
                JST
            ).isoformat()


            rows = await self.db._fetchall(

                """
                SELECT
                    id,
                    user_id,
                    channel_id,
                    message

                FROM reminders

                WHERE end_time <= ?
                """,

                (
                    now_str,
                )
            )


            if not rows:

                return


            ids = [

                row[0]

                for row
                in rows
            ]


            placeholders = ",".join(

                [
                    "?"
                    for _ in ids
                ]
            )


            await self.db._execute(

                f"""
                DELETE FROM reminders
                WHERE id IN ({placeholders})
                """,

                ids
            )


            for row in rows:

                reminder_id = row[0]

                user_id = row[1]

                channel_id = row[2]

                reminder_message = row[3]


                channel = self.get_channel(
                    channel_id
                )


                if channel:

                    try:

                        await channel.send(

                            f"⏰ <@{user_id}> "
                            f"リマインダー: {reminder_message}"
                        )


                    except discord.Forbidden:

                        logger.warning(

                            "Reminder send permission denied "
                            f"(channel={channel_id})"
                        )


                    except Exception as e:

                        logger.exception(

                            "Reminder send failed "
                            f"(id={reminder_id}): {e}"
                        )


                else:

                    logger.warning(

                        "Reminder channel not found "
                        f"(channel={channel_id})"
                    )


        except Exception as e:

            logger.exception(
                f"Reminder loop failed: {e}"
            )


    # --------------------------------------------------------------------------
    # Reminder Task 起動待ち
    # --------------------------------------------------------------------------

    @loop_reminders.before_loop

    async def before_loop_reminders(self):

        await self.wait_until_ready()


    # --------------------------------------------------------------------------
    # Monthly
    # --------------------------------------------------------------------------

    @tasks.loop(

        time=time(
            hour=7,
            minute=0,
            tzinfo=JST
        )
    )

    async def loop_monthly(self):


        if datetime.now(
            JST
        ).day != 1:

            return


        try:

            rows = await self.db._fetchall(

                """
                SELECT
                    rule_ch,
                    target_ch

                FROM monthly_rules
                """
            )


            for rule_id, target_id in rows:


                channel = self.get_channel(
                    target_id
                )


                if not channel:

                    logger.warning(

                        "Monthly target channel not found "
                        f"(channel={target_id})"
                    )

                    continue


                message = (

                    "表現の自由界隈のみなさん、おはよーさん！☀️ "
                    "新しい一ヶ月が始まったで〜！🚀\n"

                    f"📌 **ルールブック:** <#{rule_id}>\n"

                    "目を通しておいてな！"
                )


                try:

                    await channel.send(
                        message
                    )


                except discord.Forbidden:

                    logger.warning(

                        "Monthly notification permission denied "
                        f"(channel={target_id})"
                    )


                except Exception as e:

                    logger.exception(

                        "Monthly notification failed "
                        f"(channel={target_id}): {e}"
                    )


        except Exception as e:

            logger.exception(
                f"Monthly loop failed: {e}"
            )


    # --------------------------------------------------------------------------
    # Monthly Task 起動待ち
    # --------------------------------------------------------------------------

    @loop_monthly.before_loop

    async def before_loop_monthly(self):

        await self.wait_until_ready()


    # ==============================================================================
    # Message Event
    # ==============================================================================


    async def on_message(
        self,
        message
    ):


        # Bot自身・DMは無視
        if (
            message.author.bot
            or not message.guild
        ):

            return


        # ----------------------------------------------------------------------
        # Spam Check
        # ----------------------------------------------------------------------

        now = datetime.now().timestamp()


        self.spam_check[
            message.author.id
        ].append(
            now
        )


        if (
            len(
                self.spam_check[
                    message.author.id
                ]
            )
            == 5
        ):


            if (

                self.spam_check[
                    message.author.id
                ][-1]

                -

                self.spam_check[
                    message.author.id
                ][0]

                < 5
            ):


                if not (
                    message.author
                    .guild_permissions
                    .administrator
                ):


                    try:

                        await message.channel.send(

                            f"{message.author.mention} "
                            "連投はやめてな！",

                            delete_after=5
                        )


                    except Exception as e:

                        logger.exception(
                            f"Spam warning failed: {e}"
                        )


                    return


        # ----------------------------------------------------------------------
        # NG Words
        # ----------------------------------------------------------------------

        try:

            ng_words = await self.db._fetchall(

                """
                SELECT word
                FROM ng_words
                WHERE guild_id=?
                """,

                (
                    message.guild.id,
                )
            )


            for (word,) in ng_words:


                if word in message.content:


                    try:

                        await message.delete()


                        await message.channel.send(

                            f"{message.author.mention} "
                            "NGワードやで！",

                            delete_after=3
                        )


                    except discord.Forbidden:

                        logger.warning(
                            "NG word deletion permission denied."
                        )


                    except Exception as e:

                        logger.exception(
                            f"NG word moderation failed: {e}"
                        )


                    return


        except Exception as e:

            logger.exception(
                f"NG word DB check failed: {e}"
            )


        # ----------------------------------------------------------------------
        # Auto Reply
        # ----------------------------------------------------------------------

        try:

            result = await self.db._fetchone(

                """
                SELECT response
                FROM auto_replies
                WHERE guild_id=?
                AND trigger=?
                """,

                (
                    message.guild.id,
                    message.content
                )
            )


            if result:

                await message.channel.send(
                    result[0]
                )

                return


        except Exception as e:

            logger.exception(
                f"Auto reply failed: {e}"
            )


        # ----------------------------------------------------------------------
        # AI Chat
        # ----------------------------------------------------------------------

        try:

            auto_ch = await self.db.get_config(

                message.guild.id,

                "auto_chat_ch"
            )


            is_target = (

                self.user in message.mentions

                or

                message.channel.id == auto_ch
            )


            if is_target:


                if await self.db.check_daily_limit(

                    str(
                        message.author.id
                    )
                ):


                    clean_text = re.sub(

                        r"<@!?\d+>",

                        "",

                        message.content

                    ).strip()


                    if clean_text:


                        async with message.channel.typing():


                            reply = await self.ai.chat(

                                message.author.display_name,

                                clean_text
                            )


                            if (
                                not reply
                                or reply.strip() == ""
                            ):

                                reply = Config.EMPTY_MSG


                            if len(reply) > 1900:


                                file = discord.File(

                                    io.BytesIO(
                                        reply.encode()
                                    ),

                                    filename="reply.txt"
                                )


                                await message.reply(

                                    "長くなったからファイルにしたで！",

                                    file=file
                                )


                            else:

                                await message.reply(
                                    reply
                                )


                else:

                    await message.reply(

                        "今日の会話回数は終わりや。"
                        "また明日な！"
                    )


        except Exception as e:

            logger.exception(
                f"AI chat processing failed: {e}"
            )


        # ----------------------------------------------------------------------
        # XP
        # ----------------------------------------------------------------------

        try:

            leveled_up = await self.db.add_xp(

                message.author.id,

                10
            )


            if leveled_up:


                level, _ = await self.db.get_user_data(

                    message.author.id
                )


                rewards = await self.db._fetchall(

                    """
                    SELECT role_id
                    FROM level_rewards
                    WHERE guild_id=?
                    AND level<=?
                    """,

                    (
                        message.guild.id,
                        level
                    )
                )


                for reward in rewards:


                    role = message.guild.get_role(

                        reward[0]
                    )


                    if role:


                        try:

                            await message.author.add_roles(
                                role
                            )


                        except discord.Forbidden:

                            logger.warning(

                                "Level role permission denied "
                                f"(role={role.id})"
                            )


                        except Exception as e:

                            logger.exception(

                                f"Level reward failed: {e}"
                            )


                await message.channel.send(

                    f"🎉 {message.author.mention} "
                    f"レベルアップ！ (Lv.{level})"
                )


        except Exception as e:

            logger.exception(
                f"XP processing failed: {e}"
            )


    # ==============================================================================
    # Reaction Add
    # ==============================================================================


    async def on_raw_reaction_add(
        self,
        payload
    ):


        if (
            payload.member
            and payload.member.bot
        ):

            return


        # ----------------------------------------------------------------------
        # Reaction Role
        # ----------------------------------------------------------------------

        try:

            row = await self.db._fetchone(

                """
                SELECT role_id
                FROM reaction_roles
                WHERE message_id=?
                AND emoji=?
                """,

                (
                    payload.message_id,
                    str(payload.emoji)
                )
            )


            if (
                row
                and payload.member
            ):


                role = payload.member.guild.get_role(

                    row[0]
                )


                if role:

                    try:

                        await payload.member.add_roles(
                            role
                        )


                    except discord.Forbidden:

                        logger.warning(

                            "Reaction role permission denied."
                        )


                    except Exception as e:

                        logger.exception(

                            f"Reaction role add failed: {e}"
                        )


        except Exception as e:

            logger.exception(
                f"Reaction role lookup failed: {e}"
            )


        # ----------------------------------------------------------------------
        # Translation Reaction
        # ----------------------------------------------------------------------

        if (
            str(payload.emoji)
            in Config.FLAG_MAP
        ):


            try:

                channel = self.get_channel(

                    payload.channel_id
                )


                if not channel:

                    return


                message = await channel.fetch_message(

                    payload.message_id
                )


                if not message.content:

                    return


                language = Config.FLAG_MAP[

                    str(payload.emoji)
                ]


                translated = await self.ai.translate(

                    message.content,

                    language
                )


                if (
                    not translated
                    or translated.strip() == ""
                ):

                    translated = Config.ERROR_MSG


                if len(translated) > 4000:


                    file = discord.File(

                        io.BytesIO(
                            translated.encode()
                        ),

                        filename="trans.txt"
                    )


                    try:

                        if payload.member:

                            await payload.member.send(

                                "長すぎるからファイルにするな！",

                                file=file
                            )


                    except discord.Forbidden:

                        logger.info(

                            "Translation DM blocked "
                            f"(user={payload.user_id})"
                        )


                    except Exception as e:

                        logger.exception(

                            f"Translation DM failed: {e}"
                        )


                else:


                    embed = discord.Embed(

                        title=f"🌐 翻訳 ({language})",

                        description=translated,

                        color=discord.Color.blue()
                    )


                    original_preview = (

                        message.content[:50] + "..."

                        if len(
                            message.content
                        ) > 50

                        else message.content
                    )


                    embed.set_footer(

                        text=(
                            "原文: "
                            + original_preview
                        )
                    )


                    try:

                        if payload.member:

                            await payload.member.send(

                                embed=embed
                            )


                    except discord.Forbidden:

                        logger.info(

                            "Translation DM blocked "
                            f"(user={payload.user_id})"
                        )


                    except Exception as e:

                        logger.exception(

                            f"Translation DM failed: {e}"
                        )


            except Exception as e:

                logger.exception(
                    f"Reaction translation failed: {e}"
                )


        # ----------------------------------------------------------------------
        # Starboard
        # ----------------------------------------------------------------------

        if (
            str(payload.emoji)
            == "❤️"
        ):


            try:

                channel = self.get_channel(

                    payload.channel_id
                )


                if not channel:

                    return


                message = await channel.fetch_message(

                    payload.message_id
                )


                reaction = discord.utils.get(

                    message.reactions,

                    emoji="❤️"
                )


                if (
                    reaction
                    and reaction.count >= 10
                ):


                    posted = await self.db._fetchone(

                        """
                        SELECT message_id
                        FROM starboard_log
                        WHERE message_id=?
                        """,

                        (
                            message.id,
                        )
                    )


                    if posted:

                        return


                    sb_ch_id = await self.db.get_config(

                        payload.guild_id,

                        "starboard_ch"
                    )


                    if not sb_ch_id:

                        return


                    starboard_channel = self.get_channel(

                        sb_ch_id
                    )


                    if not starboard_channel:

                        logger.warning(

                            "Starboard channel not found "
                            f"(channel={sb_ch_id})"
                        )

                        return


                    embed = discord.Embed(

                        description=message.content,

                        color=discord.Color.red(),

                        timestamp=message.created_at
                    )


                    embed.set_author(

                        name=message.author.display_name,

                        icon_url=(
                            message.author
                            .display_avatar
                            .url
                        )
                    )


                    embed.add_field(

                        name="Original",

                        value=f"[Jump]({message.jump_url})"
                    )


                    if message.attachments:

                        embed.set_image(

                            url=message.attachments[0].url
                        )


                    await starboard_channel.send(

                        "いいねがたくさん。殿堂入りやね！（茜）",

                        embed=embed
                    )


                    await self.db._execute(

                        """
                        INSERT INTO starboard_log
                        (message_id)
                        VALUES (?)
                        """,

                        (
                            message.id,
                        )
                    )


            except discord.Forbidden:

                logger.warning(
                    "Starboard permission denied."
                )


            except Exception as e:

                logger.exception(
                    f"Starboard processing failed: {e}"
                )


    # ==============================================================================
    # Reaction Remove
    # ==============================================================================


    async def on_raw_reaction_remove(
        self,
        payload
    ):


        try:

            row = await self.db._fetchone(

                """
                SELECT role_id
                FROM reaction_roles
                WHERE message_id=?
                AND emoji=?
                """,

                (
                    payload.message_id,
                    str(payload.emoji)
                )
            )


            if not row:

                return


            guild = self.get_guild(

                payload.guild_id
            )


            if not guild:

                return


            member = guild.get_member(

                payload.user_id
            )


            role = guild.get_role(

                row[0]
            )


            if (
                member
                and role
            ):


                try:

                    await member.remove_roles(
                        role
                    )


                except discord.Forbidden:

                    logger.warning(

                        "Reaction role remove permission denied."
                    )


                except Exception as e:

                    logger.exception(

                        f"Reaction role remove failed: {e}"
                    )


        except Exception as e:

            logger.exception(

                f"Reaction remove processing failed: {e}"
            )


    # ==============================================================================
    # Message Delete Logging
    # ==============================================================================


    async def on_message_delete(
        self,
        message
    ):


        if message.author.bot:

            return


        if not message.guild:

            return


        try:

            log_id = await self.db.get_config(

                message.guild.id,

                "log_ch"
            )


            if not log_id:

                return


            channel = message.guild.get_channel(

                log_id
            )


            if not channel:

                return


            embed = discord.Embed(

                title="🗑️ 削除ログ",

                description=(
                    message.content
                    or "(本文なし)"
                ),

                color=discord.Color.red()
            )


            embed.set_author(

                name=message.author.display_name,

                icon_url=(
                    message.author
                    .display_avatar
                    .url
                )
            )


            embed.add_field(

                name="場所",

                value=message.channel.mention
            )


            await channel.send(
                embed=embed
            )


        except discord.Forbidden:

            logger.warning(
                "Delete log permission denied."
            )


        except Exception as e:

            logger.exception(
                f"Delete logging failed: {e}"
            )


    # ==============================================================================
    # Voice Log
    # ==============================================================================


    async def on_voice_state_update(

        self,

        member,

        before,

        after
    ):


        if before.channel == after.channel:

            return


        try:

            log_id = await self.db.get_config(

                member.guild.id,

                "log_ch"
            )


            if not log_id:

                return


            channel = member.guild.get_channel(

                log_id
            )


            if not channel:

                return


            if not before.channel:

                description = (

                    f"📥 参加: {after.channel.name}"
                )


            elif not after.channel:

                description = (

                    f"📤 退出: {before.channel.name}"
                )


            else:

                description = (

                    f"➡️ 移動: "
                    f"{before.channel.name} "
                    f"-> {after.channel.name}"
                )


            await channel.send(

                embed=discord.Embed(

                    description=(
                        f"{member.mention} "
                        f"{description}"
                    ),

                    color=discord.Color.green()
                )
            )


        except discord.Forbidden:

            logger.warning(
                "Voice log permission denied."
            )


        except Exception as e:

            logger.exception(
                f"Voice logging failed: {e}"
            )


    # ==============================================================================
    # Welcome
    # ==============================================================================


    async def on_member_join(
        self,
        member
    ):


        try:

            welcome_id = await self.db.get_config(

                member.guild.id,

                "welcome_ch"
            )


            if not welcome_id:

                return


            channel = member.guild.get_channel(

                welcome_id
            )


            if channel:

                await channel.send(

                    f"{member.mention} "
                    "表現の自由界隈サーバーへようこそ。"
                    "このサーバーのマスコットキャラクターの"
                    "表自派茜（ひょうじは あかね）やで！ "
                    "ゆっくりしていってな！"
                )


        except discord.Forbidden:

            logger.warning(
                "Welcome message permission denied."
            )


        except Exception as e:

            logger.exception(
                f"Welcome message failed: {e}"
            )


# ==============================================================================
# Bot Instance
# ==============================================================================


bot = AkaneBot()


# ==============================================================================
# 6. 一般コマンド
# ==============================================================================


# ==============================================================================
# Translate
# ==============================================================================


@bot.tree.command(

    name="translate",

    description="AI翻訳"
)

@app_commands.describe(

    language="翻訳先の言語",

    text="原文"
)

async def translate(

    interaction: discord.Interaction,

    language: str,

    text: str
):


    await interaction.response.defer()


    try:

        result = await bot.ai.translate(

            text,

            language
        )


        if (
            not result
            or result.strip() == ""
        ):

            result = Config.ERROR_MSG


        if len(result) > 4000:


            file = discord.File(

                io.BytesIO(
                    result.encode()
                ),

                filename="trans.txt"
            )


            await interaction.followup.send(

                "長すぎるからファイルにするな！",

                file=file
            )


        else:


            embed = discord.Embed(

                title=f"翻訳 ({language})",

                description=result,

                color=discord.Color.blue()
            )


            await interaction.followup.send(

                embed=embed
            )


    except Exception as e:

        logger.exception(
            f"/translate failed: {e}"
        )


        await interaction.followup.send(

            "翻訳中にエラーが起きたで。",

            ephemeral=True
        )


# ==============================================================================
# Define
# ==============================================================================


@bot.tree.command(

    name="define",

    description="AI辞書 (400文字解説)"
)

@app_commands.describe(

    word="言葉",

    wiki_mode="Wikipedia優先モード"
)

async def define(

    interaction: discord.Interaction,

    word: str,

    wiki_mode: bool = False
):


    await interaction.response.defer()


    try:

        result = await bot.ai.define_word(

            word,

            wiki_mode
        )


        if (
            not result
            or result.strip() == ""
        ):


            await interaction.followup.send(

                Config.ERROR_MSG,

                ephemeral=True
            )

            return


        if len(result) > 4000:


            file = discord.File(

                io.BytesIO(
                    result.encode()
                ),

                filename="define.txt"
            )


            await interaction.followup.send(

                "長すぎるからファイルにするな！",

                file=file
            )

            return


        title = (

            f"📖 辞書: {word}"

            + (
                " (Wiki Mode)"
                if wiki_mode
                else ""
            )
        )


        embed = discord.Embed(

            title=title,

            description=result,

            color=discord.Color.green()
        )


        embed.set_footer(

            text="Powered by AI Dictionary"
        )


        await interaction.followup.send(

            embed=embed
        )


    except Exception as e:

        logger.exception(
            f"/define failed: {e}"
        )


        await interaction.followup.send(

            "辞書処理中にエラーが起きたで。",

            ephemeral=True
        )


# ==============================================================================
# Summary
# ==============================================================================


@bot.tree.command(

    name="summary",

    description="自分の発言要約"
)

@app_commands.describe(

    back="過去何件遡るか(最大20)"
)

async def summary(

    interaction: discord.Interaction,

    back: int
):


    if back < 1:

        back = 1


    if back > 20:

        back = 20


    await interaction.response.defer(
        ephemeral=True
    )


    try:

        messages = [

            message.content

            async for message
            in interaction.channel.history(
                limit=100
            )

            if message.author
            == interaction.user
        ][:back]


        if not messages:


            await interaction.followup.send(

                "発言が見つからんかったわ。",

                ephemeral=True
            )

            return


        messages.reverse()


        result = await bot.ai.summarize(

            messages
        )


        if (
            not result
            or result.strip() == ""
        ):

            result = Config.ERROR_MSG


        if len(result) > 4000:


            file = discord.File(

                io.BytesIO(
                    result.encode()
                ),

                filename="summary.txt"
            )


            await interaction.followup.send(

                "長すぎるからファイルにするな！",

                file=file,

                ephemeral=True
            )


        else:


            embed = discord.Embed(

                title="📝 発言要約",

                description=result,

                color=discord.Color.orange()
            )


            await interaction.followup.send(

                embed=embed,

                ephemeral=True
            )


    except discord.Forbidden:

        await interaction.followup.send(

            "チャンネル履歴を見る権限がないみたいや。",

            ephemeral=True
        )


    except Exception as e:

        logger.exception(
            f"/summary failed: {e}"
        )


        await interaction.followup.send(

            "要約中にエラーが起きたで。",

            ephemeral=True
        )


# ==============================================================================
# Event
# ==============================================================================


@bot.tree.command(

    name="event",

    description="イベント(スケジュール)作成"
)

@app_commands.describe(

    title="イベント名",

    date="日付 YYYY/MM/DD",

    time="時刻 HH:MM"
)

async def event(

    interaction: discord.Interaction,

    title: str,

    date: str,

    time: str
):


    # --------------------------------------------------------------------------
    # 日時変換
    # --------------------------------------------------------------------------

    try:

        datetime_text = (

            f"{date} {time}"
        )


        naive_datetime = datetime.strptime(

            datetime_text,

            "%Y/%m/%d %H:%M"
        )


        event_datetime = JST.localize(

            naive_datetime
        )


    except ValueError:


        await interaction.response.send_message(

            "日時は `YYYY/MM/DD HH:MM` "
            "の形式で頼むで！",

            ephemeral=True
        )

        return


    timestamp = int(

        event_datetime.timestamp()
    )


    embed = discord.Embed(

        title=f"📅 {title}",

        description=(
            f"日時: <t:{timestamp}:F>"
        ),

        color=discord.Color.green()
    )


    # EventView側と名前を統一
    embed.add_field(

        name="【参加】",

        value="なし"
    )


    embed.add_field(

        name="【不参加】",

        value="なし"
    )


    try:

        await interaction.response.send_message(

            embed=embed,

            view=EventView()
        )


    except Exception as e:

        logger.exception(

            f"Event message creation failed: {e}"
        )

        return


    # --------------------------------------------------------------------------
    # Discord Scheduled Event
    # --------------------------------------------------------------------------

    try:

        await interaction.guild.create_scheduled_event(

            name=title,

            start_time=event_datetime,

            end_time=(
                event_datetime
                + timedelta(hours=2)
            ),

            location="Discord",

            entity_type=(
                discord.EntityType.external
            ),

            privacy_level=(
                discord.PrivacyLevel.guild_only
            )
        )


    except discord.Forbidden:

        logger.warning(

            "Scheduled event permission denied "
            f"(guild={interaction.guild.id})"
        )


    except Exception as e:

        logger.exception(

            f"Scheduled event creation failed: {e}"
        )


# ==============================================================================
# Poll
# ==============================================================================


@bot.tree.command(

    name="poll",

    description="投票作成"
)

async def poll(

    interaction: discord.Interaction,

    question: str,

    option1: str,

    option2: str,

    option3: Optional[str] = None,

    option4: Optional[str] = None
):


    options = [

        option

        for option
        in [
            option1,
            option2,
            option3,
            option4
        ]

        if option
    ]


    emojis = [

        "1️⃣",
        "2️⃣",
        "3️⃣",
        "4️⃣"
    ]


    description = "\n".join(

        [

            f"{emojis[index]} {option}"

            for index, option
            in enumerate(options)
        ]
    )


    try:

        await interaction.response.send_message(

            f"📊 **{question}** #投票",

            embed=discord.Embed(

                description=description,

                color=discord.Color.gold()
            )
        )


        message = await interaction.original_response()


        for index in range(
            len(options)
        ):

            await message.add_reaction(

                emojis[index]
            )


    except discord.Forbidden:

        logger.warning(
            "Poll reaction permission denied."
        )


    except Exception as e:

        logger.exception(
            f"/poll failed: {e}"
        )


# ==============================================================================
# Search
# ==============================================================================


@bot.tree.command(

    name="search",

    description="検索"
)

@app_commands.describe(

    keyword="語句",

    target_channel="ch",

    member="人",

    days="期間"
)

async def search(

    interaction: discord.Interaction,

    keyword: str,

    target_channel: Optional[
        discord.TextChannel
    ] = None,

    member: Optional[
        discord.Member
    ] = None,

    days: Optional[int] = None
):


    await interaction.response.defer(
        ephemeral=True
    )


    channel = (

        target_channel

        if target_channel

        else interaction.channel
    )


    after = (

        datetime.now(pytz.utc)
        - timedelta(days=days)

        if days

        else None
    )


    found = []


    try:

        async for message in channel.history(

            limit=1000,

            after=after
        ):


            if (
                member
                and message.author != member
            ):

                continue


            if keyword in message.content:


                found.append(
                    message
                )


                if len(found) >= 100:

                    break


    except discord.Forbidden:


        await interaction.followup.send(

            "そのチャンネルの履歴を見る権限がないみたいや。",

            ephemeral=True
        )

        return


    except Exception as e:


        logger.exception(

            f"Message search failed: {e}"
        )


        await interaction.followup.send(

            "検索中にエラーが発生したで。",

            ephemeral=True
        )

        return


    if not found:


        await interaction.followup.send(

            "なし",

            ephemeral=True
        )

        return


    if len(found) > 20:


        text = "\n".join(

            [

                f"[{message.created_at}] "
                f"{message.author}: "
                f"{message.content}"

                for message
                in found
            ]
        )


        file = discord.File(

            io.BytesIO(
                text.encode()
            ),

            filename="result.txt"
        )


        await interaction.followup.send(

            f"{len(found)}件 (ファイル)",

            file=file,

            ephemeral=True
        )


    else:


        description = "\n".join(

            [

                f"• [{message.content[:30]}]"
                f"({message.jump_url})"

                for message
                in found
            ]
        )


        embed = discord.Embed(

            title=f"検索: {keyword}",

            description=description
        )


        await interaction.followup.send(

            embed=embed,

            ephemeral=True
        )


# ==============================================================================
# Level
# ==============================================================================


@bot.tree.command(

    name="level",

    description="レベル確認"
)

async def level(

    interaction: discord.Interaction
):


    try:

        level_value, xp = await bot.db.get_user_data(

            interaction.user.id
        )


        await interaction.response.send_message(

            f"📊 Lv.{level_value} (XP: {xp})",

            ephemeral=True
        )


    except Exception as e:

        logger.exception(
            f"/level failed: {e}"
        )


        await interaction.response.send_message(

            "レベル情報の取得中にエラーが起きたで。",

            ephemeral=True
        )


# ==============================================================================
# Leaderboard
# ==============================================================================


@bot.tree.command(

    name="leaderboard",

    description="ランキング(TOP30)"
)

async def leaderboard(

    interaction: discord.Interaction
):


    await interaction.response.defer(
        ephemeral=True
    )


    try:

        rows = await bot.db.get_leaderboard(
            30
        )


        text = ""


        for index, (
            user_id,
            level_value,
            xp
        ) in enumerate(
            rows,
            1
        ):


            member = interaction.guild.get_member(

                int(user_id)
            )


            name = (

                member.display_name

                if member

                else "Unknown"
            )


            text += (

                f"{index}. "
                f"{name} "
                f"(Lv.{level_value})\n"
            )


        embed = discord.Embed(

            title="🏆 ランキング",

            description=(
                text
                or "データなし"
            ),

            color=discord.Color.gold()
        )


        await interaction.followup.send(

            embed=embed,

            ephemeral=True
        )


    except Exception as e:

        logger.exception(
            f"/leaderboard failed: {e}"
        )


        await interaction.followup.send(

            "ランキング取得中にエラーが起きたで。",

            ephemeral=True
        )


# ==============================================================================
# Reminder
# ==============================================================================


@bot.tree.command(

    name="remind",

    description="リマインダー"
)

@app_commands.describe(

    minutes="何分後に通知するか",

    message="通知する内容"
)

async def remind(

    interaction: discord.Interaction,

    minutes: int,

    message: str
):


    # 最低1分
    if minutes < 1:


        await interaction.response.send_message(

            "1分以上を指定してな！",

            ephemeral=True
        )

        return


    # 最大7日
    if minutes > 10080:


        await interaction.response.send_message(

            "今のところ最大7日（10080分）までにしてな！",

            ephemeral=True
        )

        return


    # 文字数制限
    if len(message) > 500:


        await interaction.response.send_message(

            "リマインダーの文章は500文字以内にしてな！",

            ephemeral=True
        )

        return


    try:

        await bot.db.add_reminder(

            interaction.user.id,

            interaction.channel.id,

            message,

            minutes
        )


        await interaction.response.send_message(

            f"⏰ {minutes}分後に"
            f"「{message}」って知らせるで！",

            ephemeral=True
        )


    except Exception as e:


        logger.exception(

            f"Reminder registration failed: {e}"
        )


        if not interaction.response.is_done():


            await interaction.response.send_message(

                "リマインダーの登録中にエラーが起きたで。",

                ephemeral=True
            )


# ==============================================================================
# 7. 起動
# ==============================================================================


if __name__ == "__main__":


    if not DISCORD_TOKEN:


        logger.error(
            "DISCORD_TOKEN is missing."
        )


    else:


        logger.info(
            "=============================================="
        )

        logger.info(
            "Akane Bot v27 starting..."
        )

        logger.info(
            f"Database path: {Config.DB_NAME}"
        )

        logger.info(
            f"AI model: {Config.GPT_MODEL}"
        )

        logger.info(
            "=============================================="
        )


        bot.run(
            DISCORD_TOKEN
        )
