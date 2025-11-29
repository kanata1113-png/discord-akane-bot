import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
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
# 0. 初期設定 & 定数
# ==============================================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AkaneBot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
JST = pytz.timezone('Asia/Tokyo')

class Config:
    GPT_MODEL = "gpt-5-mini"
    DB_NAME = '/data/akane_v19.db' if os.path.exists("/data") else 'akane_v19.db'
    
    # ★修正箇所: 変数名を呼び出し側と一致させました
    NORMAL_CHAT_MAX_TOKENS = 1500
    DAILY_LIMIT = 100
    
    # 茜ちゃんの性格トリガー
    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '制限', '禁止', '表現の自由', '言論統制', '弾圧', 'ポリコレ']
    
    # 国旗翻訳マップ
    FLAG_MAP = {
        "🇺🇸": "English", "🇬🇧": "English", "🇨🇦": "English", "🇦🇺": "English",
        "🇯🇵": "Japanese", "🇨🇳": "Chinese", "🇰🇷": "Korean", "🇫🇷": "French",
        "🇩🇪": "German", "🇮🇹": "Italian", "🇪🇸": "Spanish", "🇷🇺": "Russian",
        "🇻🇳": "Vietnamese", "🇹🇭": "Thai", "🇮🇩": "Indonesian"
    }

if OPENAI_API_KEY:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None
    logger.warning("OpenAI API Key is missing.")

# ==============================================================================
# 1. データベース管理 (DatabaseManager)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_path):
        self.path = db_path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            # ログ・分析・履歴
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (user_id TEXT, date TEXT, count INTEGER DEFAULT 0, UNIQUE(user_id, date))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS starboard_log (message_id INTEGER PRIMARY KEY)''')
            
            # 設定
            await db.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_ch INTEGER,
                log_ch INTEGER,
                starboard_ch INTEGER,
                auto_chat_ch INTEGER
            )''')
            
            # ユーザーデータ
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            
            # 機能データ
            await db.execute('''CREATE TABLE IF NOT EXISTS level_rewards (guild_id INTEGER, level INTEGER, role_id INTEGER, PRIMARY KEY(guild_id, level))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS ng_words (guild_id INTEGER, word TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, trigger TEXT, response TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, message TEXT, end_time TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS monthly_rules (guild_id INTEGER PRIMARY KEY, rule_ch INTEGER, target_ch INTEGER)''')
            
            await db.commit()
        logger.info(f"Database initialized: {self.path}")

    # --- 汎用ヘルパー ---
    async def _execute(self, query, params=()):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(query, params)
            await db.commit()

    async def _fetchone(self, query, params=()):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()

    async def _fetchall(self, query, params=()):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()

    # --- 設定関連 ---
    async def set_config(self, guild_id: int, col: str, val: int):
        current = await self._fetchone("SELECT guild_id FROM guild_settings WHERE guild_id=?", (guild_id,))
        if current:
            await self._execute(f"UPDATE guild_settings SET {col}=? WHERE guild_id=?", (val, guild_id))
        else:
            await self._execute(f"INSERT INTO guild_settings (guild_id, {col}) VALUES (?, ?)", (guild_id, val))

    async def get_config(self, guild_id: int, col: str) -> Optional[int]:
        res = await self._fetchone(f"SELECT {col} FROM guild_settings WHERE guild_id=?", (guild_id,))
        return res[0] if res else None

    # --- XP関連 ---
    async def add_xp(self, user_id: int, amount: int = 10) -> bool:
        row = await self._fetchone("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
        if row:
            xp, level = row
            xp += amount
            is_up = False
            if xp >= level * 100:
                xp = 0
                level += 1
                is_up = True
            await self._execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (xp, level, user_id))
            return is_up
        else:
            await self._execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (user_id, amount, 1))
            return False

    async def get_user_data(self, user_id: int):
        res = await self._fetchone("SELECT level, xp FROM users WHERE user_id=?", (user_id,))
        return res if res else (1, 0)

    async def get_leaderboard(self, limit=30):
        return await self._fetchall("SELECT user_id, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT ?", (limit,))

    # --- その他機能 ---
    async def check_daily_limit(self, user_id: str) -> bool:
        today = datetime.now(JST).strftime('%Y-%m-%d')
        row = await self._fetchone("SELECT count FROM usage_log WHERE user_id=? AND date=?", (user_id, today))
        count = row[0] if row else 0
        if count >= Config.DAILY_LIMIT: return False
        
        if row:
            await self._execute("UPDATE usage_log SET count=count+1 WHERE user_id=? AND date=?", (user_id, today))
        else:
            await self._execute("INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, 1)", (user_id, today))
        return True

# ==============================================================================
# 2. AIロジック (AiManager)
# ==============================================================================
class AiManager:
    def __init__(self):
        self.model = Config.GPT_MODEL

    async def call_gpt(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if not openai_client: return "APIキーが設定されてへんで！"
        
        is_reasoning = "gpt-5" in self.model or "o1" in self.model
        
        try:
            params = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]
            }
            
            if is_reasoning:
                params["max_completion_tokens"] = max_tokens
                params["reasoning_effort"] = "medium"
            else:
                params["max_tokens"] = max_tokens
                params["temperature"] = 0.7

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: openai_client.chat.completions.create(**params))
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Error: {e}")
            return f"あかん、エラーが出てもうた... ({e})"

    async def chat(self, user_name: str, content: str) -> str:
        is_high_tension = any(k in content for k in Config.REGULATION_KEYWORDS)
        
        style = "基本的には親しみやすく、友達のような関西弁で振る舞ってください。"
        if is_high_tension:
            style = "【重要】今は「表現の自由」に関する話題が出ています。スイッチが入ったようにテンションを上げ、非常に熱く、情熱的に語ってください。"

        system = (
            f"あなたは「表自派茜（ひょうじは あかね）」という元気な関西弁の女子高生AIです。\n"
            f"一人称は「茜」です。ユーザー名は「{user_name}」です。\n{style}\n"
            "ルール：\n"
            "1. 日本語・関西弁で話す。\n"
            "2. 回答は必ず1000文字以内。\n"
            "3. 文字数を超えそうな場合は途中で切り上げ、「まだ話し足りないけど、字数の制限があるからいったんここらで切り上げるわ。気になることがあったらまた声をかけてな！」と付け加える。"
        )
        return await self.call_gpt(system, content, max_tokens=Config.NORMAL_CHAT_MAX_TOKENS)

    async def translate(self, text: str, target_lang: str) -> str:
        sys = f"Translate the user input to {target_lang}. Output ONLY the translated text."
        return await self.call_gpt(sys, text)

    async def define_word(self, word: str, wiki_mode: bool) -> str:
        sys = f"あなたは親切な辞書です。「{word}」の意味を、200文字程度で要約して解説してください。"
        if wiki_mode: sys += " (Wikipedia等の信頼できる情報をソースとして優先してください)"
        return await self.call_gpt(sys, word, max_tokens=500)

    async def summarize(self, text_list: List[str]) -> str:
        joined = "\n".join(text_list)
        sys = "以下のユーザーの発言ログを読み、要点を400文字以内で簡潔に要約してください。一人称は「茜」で、関西弁で説明してください。"
        return await self.call_gpt(sys, joined, max_tokens=800)

# ==============================================================================
# 3. UIコンポーネント (Views)
# ==============================================================================
class EventView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, custom_id="ev_join")
    async def join(self, i: discord.Interaction, b: discord.ui.Button):
        await self._update(i, "参加")
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger, custom_id="ev_leave")
    async def leave(self, i: discord.Interaction, b: discord.ui.Button):
        await self._update(i, "不参加")
    
    async def _update(self, i, status):
        embed = i.message.embeds[0]
        new_fields = []
        target = f"【{status}】"
        for f in embed.fields:
            vals = [l for l in f.value.split('\n') if i.user.mention not in l and "なし" not in l]
            if f.name == target: vals.append(f"• {i.user.mention}")
            new_fields.append((f.name, '\n'.join(vals) or "なし"))
        
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
        new_embed.set_footer(text=embed.footer.text)
        new_embed.timestamp = embed.timestamp
        for n, v in new_fields: new_embed.add_field(name=n, value=v)
        await i.response.edit_message(embed=new_embed)

class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="問い合わせ", style=discord.ButtonStyle.primary, emoji="📩", custom_id="tk_open")
    async def create(self, i: discord.Interaction, b: discord.ui.Button):
        overwrites = {
            i.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True),
            i.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}", overwrites=overwrites)
        await i.response.send_message(f"個室を作ったで！こちらへどうぞ: {ch.mention}", ephemeral=True)
        await ch.send(f"{i.user.mention} ここは他の人には見えへんから、安心して要件を書いてな。", view=TicketCloseView())

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="解決・閉じる", style=discord.ButtonStyle.danger, custom_id="tk_close")
    async def close(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_message("ほな閉じるで〜")
        await asyncio.sleep(3)
        await i.channel.delete()

# ==============================================================================
# 4. Bot本体
# ==============================================================================
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        self.db = DatabaseManager(Config.DB_NAME)
        self.ai = AiManager()
        self.spam_check = defaultdict(lambda: deque(maxlen=5))

    async def setup_hook(self):
        await self.db.init()
        self.add_view(EventView())
        self.add_view(TicketView())
        self.add_view(TicketCloseView())
        
        self.loop_reminders.start()
        self.loop_monthly.start()

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.tree.sync()

    # --- 定期タスク ---
    @tasks.loop(seconds=60)
    async def loop_reminders(self):
        now_str = datetime.now(JST).isoformat()
        rows = await self.db._fetchall("SELECT id, user_id, channel_id, message FROM reminders WHERE end_time <= ?", (now_str,))
        if rows:
            ids = [r[0] for r in rows]
            await self.db._execute(f"DELETE FROM reminders WHERE id IN ({','.join(['?']*len(ids))})", ids)
            for r in rows:
                ch = self.get_channel(r[2])
                if ch: await ch.send(f"⏰ <@{r[1]}> リマインダー: {r[3]}")

    @tasks.loop(time=time(hour=7, minute=0, tzinfo=JST))
    async def loop_monthly(self):
        if datetime.now(JST).day != 1: return
        rows = await self.db._fetchall("SELECT rule_ch, target_ch FROM monthly_rules")
        for rule_id, target_id in rows:
            ch = self.get_channel(target_id)
            if ch:
                msg = (
                    "表現の自由界隈のみなさん、おはよーさん！☀️ 新しい一ヶ月が始まったで〜！🚀\n"
                    "こちらはサーバーのルールブックになりますので、まだ未読の方はこれを機に目を通しておいてください。👀✨\n"
                    "今月もまたよろしくな！💪🔥\n\n"
                    f"📌 **ルールブック:** <#{rule_id}>"
                )
                try: await ch.send(msg)
                except: pass

    # --- イベントハンドラ ---
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        
        # モデレーション
        if await self.check_moderation(message): return
        
        # 自動応答
        res = await self.db._fetchone("SELECT response FROM auto_replies WHERE guild_id=? AND trigger=?", (message.guild.id, message.content))
        if res:
            await message.channel.send(res[0])
            return

        # AIチャット (メンション or 常駐)
        auto_ch = await self.db.get_config(message.guild.id, "auto_chat_ch")
        is_target = (self.user in message.mentions) or (message.channel.id == auto_ch)
        
        if is_target:
            if await self.db.check_daily_limit(str(message.author.id)):
                clean_text = re.sub(r'<@!?\d+>', '', message.content).strip()
                if clean_text:
                    async with message.channel.typing():
                        reply = await self.ai.chat(message.author.display_name, clean_text)
                        if len(reply) > 1900:
                            f = discord.File(io.BytesIO(reply.encode()), filename="reply.txt")
                            await message.reply("長くなったからファイルにしたで！", file=f)
                        else:
                            await message.reply(reply)
            else:
                await message.reply("今日の会話回数は終わりや。また明日な！")

        # XP加算
        if await self.db.add_xp(message.author.id, 10):
            # レベルアップ報酬
            lv, _ = await self.db.get_user_data(message.author.id)
            rewards = await self.db._fetchall("SELECT role_id FROM level_rewards WHERE guild_id=? AND level<=?", (message.guild.id, lv))
            for r in rewards:
                role = message.guild.get_role(r[0])
                if role: await message.author.add_roles(role)
            await message.channel.send(f"🎉 {message.author.mention} レベルアップしたで！ (Lv.{lv})")

    async def check_moderation(self, message):
        if message.author.guild_permissions.administrator: return False
        
        # 招待リンク
        if re.search(r'(discord\.gg|discord\.com\/invite)\/', message.content):
            await message.delete()
            return True
        
        # NGワード
        ngs = await self.db._fetchall("SELECT word FROM ng_words WHERE guild_id=?", (message.guild.id,))
        for (word,) in ngs:
            if word in message.content:
                await message.delete()
                await message.channel.send(f"{message.author.mention} NGワードやで！", delete_after=3)
                return True
        return False

    async def on_raw_reaction_add(self, payload):
        if payload.member.bot: return
        
        # リアクションロール
        row = await self.db._fetchone("SELECT role_id FROM reaction_roles WHERE message_id=? AND emoji=?", (payload.message_id, str(payload.emoji)))
        if row:
            role = payload.member.guild.get_role(row[0])
            if role: await payload.member.add_roles(role)

        # 国旗翻訳
        if str(payload.emoji) in Config.FLAG_MAP:
            ch = self.get_channel(payload.channel_id)
            msg = await ch.fetch_message(payload.message_id)
            if msg.content:
                lang = Config.FLAG_MAP[str(payload.emoji)]
                trans = await self.ai.translate(msg.content, lang)
                embed = discord.Embed(title=f"🌐 翻訳 ({lang})", description=trans, color=discord.Color.blue())
                try: await payload.member.send(embed=embed)
                except: pass

        # 殿堂入り
        if str(payload.emoji) == "❤️":
            ch = self.get_channel(payload.channel_id)
            msg = await ch.fetch_message(payload.message_id)
            reaction = discord.utils.get(msg.reactions, emoji="❤️")
            if reaction and reaction.count >= 10:
                posted = await self.db._fetchone("SELECT message_id FROM starboard_log WHERE message_id=?", (msg.id,))
                if not posted:
                    sb_ch_id = await self.db.get_config(payload.guild_id, "starboard_ch")
                    if sb_ch_id:
                        sb_ch = self.get_channel(sb_ch_id)
                        embed = discord.Embed(description=msg.content, color=discord.Color.red(), timestamp=msg.created_at)
                        embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
                        embed.add_field(name="Original", value=f"[Jump]({msg.jump_url})")
                        if msg.attachments: embed.set_image(url=msg.attachments[0].url)
                        await sb_ch.send("いいねがたくさん。殿堂入りやね！（茜）", embed=embed)
                        await self.db._execute("INSERT INTO starboard_log (message_id) VALUES (?)", (msg.id,))

    async def on_raw_reaction_remove(self, payload):
        row = await self.db._fetchone("SELECT role_id FROM reaction_roles WHERE message_id=? AND emoji=?", (payload.message_id, str(payload.emoji)))
        if row:
            guild = self.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(row[0])
            if member and role: await member.remove_roles(role)

    # ログ
    async def on_message_delete(self, message):
        if message.author.bot: return
        log_id = await self.db.get_config(message.guild.id, "log_ch")
        if log_id:
            ch = message.guild.get_channel(log_id)
            if ch:
                embed = discord.Embed(title="🗑️ 削除ログ", description=message.content, color=discord.Color.red())
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                embed.add_field(name="場所", value=message.channel.mention)
                await ch.send(embed=embed)

    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel: return
        log_id = await self.db.get_config(member.guild.id, "log_ch")
        if log_id:
            ch = member.guild.get_channel(log_id)
            desc = ""
            if not before.channel: desc = f"📥 参加: {after.channel.name}"
            elif not after.channel: desc = f"📤 退出: {before.channel.name}"
            else: desc = f"➡️ 移動: {before.channel.name} -> {after.channel.name}"
            await ch.send(embed=discord.Embed(description=f"{member.mention} {desc}", color=discord.Color.green()))

    async def on_member_join(self, member):
        wc_id = await self.db.get_config(member.guild.id, "welcome_ch")
        if wc_id:
            ch = member.guild.get_channel(wc_id)
            if ch: await ch.send(f"{member.mention} 表現の自由界隈サーバーへようこそ。このサーバーのマスコットキャラクターの表自派茜（ひょうじは あかね）やで！ ゆっくりしていってな！")

bot = AkaneBot()

# ==============================================================================
# 5. コマンド定義 (Group化して整理)
# ==============================================================================

# --- 管理者グループ (Admin) ---
class AdminCommands(app_commands.Group):
    def __init__(self): super().__init__(name="admin", description="サーバー管理コマンド")

    @app_commands.command(name="config_log", description="監査ログのチャンネル設定")
    async def config_log(self, i: discord.Interaction, channel: discord.TextChannel):
        await bot.db.set_config(i.guild.id, "log_ch", channel.id)
        await i.response.send_message(f"ログ出力先: {channel.mention}", ephemeral=True)

    @app_commands.command(name="config_welcome", description="挨拶チャンネル設定")
    async def config_welcome(self, i: discord.Interaction, channel: discord.TextChannel):
        await bot.db.set_config(i.guild.id, "welcome_ch", channel.id)
        await i.response.send_message(f"挨拶場所: {channel.mention}", ephemeral=True)

    @app_commands.command(name="config_starboard", description="殿堂入りチャンネル設定")
    async def config_starboard(self, i: discord.Interaction, channel: discord.TextChannel):
        await bot.db.set_config(i.guild.id, "starboard_ch", channel.id)
        await i.response.send_message(f"殿堂入り先: {channel.mention}", ephemeral=True)

    @app_commands.command(name="config_autochat", description="常駐自動応答チャンネル設定")
    async def
