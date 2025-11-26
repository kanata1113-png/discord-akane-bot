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
from collections import defaultdict, deque
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ==============================================================================
# 0. 環境変数・ログ・共通設定
# ==============================================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class OpenAIConfig:
    GPT_MODEL = "gpt-5.1"

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    if os.path.exists("/data"):
        DB_NAME = '/data/akane_final_v12.db'
    else:
        DB_NAME = 'akane_final_v12.db'

    REGULATION_ANALYSIS_MAX_TOKENS = 2000
    NORMAL_CHAT_MAX_TOKENS = 800
    GPT_MODEL = OpenAIConfig.GPT_MODEL

    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '制限', '禁止', '表現の自由', '言論統制', '弾圧']
    QUESTION_KEYWORDS = ['妥当', '適切', '正しい', 'どう思う', '判断', '評価', '分析']

    FLAG_MAPPING = {
        "🇺🇸": "English", "🇬🇧": "English", "🇨🇦": "English",
        "🇯🇵": "Japanese", "🇨🇳": "Chinese", "🇰🇷": "Korean",
        "🇫🇷": "French", "🇩🇪": "German", "🇮🇹": "Italian",
        "🇪🇸": "Spanish", "🇷🇺": "Russian", "🇻🇳": "Vietnamese",
        "🇹🇭": "Thai", "🇮🇩": "Indonesian"
    }

# ==============================================================================
# 1. データベース管理
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # ログ・履歴
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, count INTEGER DEFAULT 0, UNIQUE(user_id, date))''')
            # 設定
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, autorole_id INTEGER, welcome_channel_id INTEGER, log_channel_id INTEGER, starboard_channel_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS monthly_settings (guild_id INTEGER PRIMARY KEY, rule_channel_id INTEGER, target_channel_id INTEGER)''')
            # ユーザー・その他
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS level_rewards (guild_id INTEGER, level INTEGER, role_id INTEGER, PRIMARY KEY(guild_id, level))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS ng_words (guild_id INTEGER, word TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, trigger TEXT, response TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, message TEXT, end_time TEXT)''')
            # 殿堂入りログ
            await db.execute('''CREATE TABLE IF NOT EXISTS starboard_log (message_id INTEGER PRIMARY KEY)''')
            
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    # --- 設定系 ---
    async def set_channel_setting(self, guild_id: int, col_name: str, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", (guild_id,))
            if await cursor.fetchone():
                await db.execute(f"UPDATE settings SET {col_name} = ? WHERE guild_id = ?", (channel_id, guild_id))
            else:
                await db.execute(f"INSERT INTO settings (guild_id, {col_name}) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def get_channel_setting(self, guild_id: int, col_name: str) -> Optional[int]:
        async with aiosqlite.connect(self.db_name) as db:
            try:
                cursor = await db.execute(f"SELECT {col_name} FROM settings WHERE guild_id = ?", (guild_id,))
                row = await cursor.fetchone()
                return row[0] if row else None
            except: return None

    async def set_monthly_rule(self, guild_id: int, rule_ch_id: int, target_ch_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT OR REPLACE INTO monthly_settings (guild_id, rule_channel_id, target_channel_id) VALUES (?, ?, ?)", (guild_id, rule_ch_id, target_ch_id))
            await db.commit()

    async def get_all_monthly_settings(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id, rule_channel_id, target_channel_id FROM monthly_settings")
            return await cursor.fetchall()

    # --- XP系 ---
    async def add_xp(self, user_id: int, amount: int) -> tuple[int, int, bool]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                xp, level = row
                xp += amount
                if xp >= level * 100: xp = 0; level += 1; is_levelup = True
                else: is_levelup = False
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
            else:
                xp, level = amount, 1; is_levelup = False
                await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (user_id, xp, level))
            await db.commit()
            return xp, level, is_levelup

    # --- リアクションロール ---
    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)", (message_id, emoji, role_id))
            await db.commit()

    async def get_reaction_role(self, message_id: int, emoji: str):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
            row = await cursor.fetchone()
            return row[0] if row else None

    # --- 殿堂入りログ ---
    async def is_starboard_posted(self, message_id: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT message_id FROM starboard_log WHERE message_id = ?", (message_id,))
            return await cursor.fetchone() is not None

    async def add_starboard_log(self, message_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO starboard_log (message_id) VALUES (?)", (message_id,))
            await db.commit()

    # --- その他便利機能 ---
    async def add_ng_word(self, guild_id, word):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO ng_words (guild_id, word) VALUES (?, ?)", (guild_id, word))
            await db.commit()
    async def get_ng_words(self, guild_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT word FROM ng_words WHERE guild_id = ?", (guild_id,))
            return [r[0] for r in await cursor.fetchall()]
    
    async def add_auto_reply(self, guild_id, trigger, response):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO auto_replies (guild_id, trigger, response) VALUES (?, ?, ?)", (guild_id, trigger, response))
            await db.commit()
    async def get_auto_reply(self, guild_id, content):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT response FROM auto_replies WHERE guild_id = ? AND trigger = ?", (guild_id, content))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def add_reminder(self, user_id, channel_id, message, minutes):
        end = (datetime.now(JST) + timedelta(minutes=minutes)).isoformat()
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO reminders (user_id, channel_id, message, end_time) VALUES (?, ?, ?, ?)", (user_id, channel_id, message, end))
            await db.commit()
    async def check_reminders(self):
        now = datetime.now(JST).isoformat()
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT id, user_id, channel_id, message FROM reminders WHERE end_time <= ?", (now,))
            rows = await cursor.fetchall()
            if rows:
                ids = [r[0] for r in rows]
                await db.execute(f"DELETE FROM reminders WHERE id IN ({','.join(['?']*len(ids))})", ids)
                await db.commit()
            return rows

    async def check_usage(self, user_id: str) -> bool:
        today = datetime.now(JST).strftime('%Y-%m-%d')
        async with aiosqlite.connect(self.db_name) as db:
            c = await db.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
            res = await c.fetchone()
            count = res[0] if res else 0
            if count >= BotConfig.DAILY_MESSAGE_LIMIT: return False
            if res: await db.execute('UPDATE usage_log SET count = count + 1 WHERE user_id = ? AND date = ?', (user_id, today))
            else: await db.execute('INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, 1)', (user_id, today))
            await db.commit()
            return True

# ==============================================================================
# 2. ロジック & Views
# ==============================================================================

class ScheduleView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    async def update(self, i, status):
        embed = i.message.embeds[0]; user = i.user; target = f"【{status}】"
        new_fields = []
        for field in embed.fields:
            lines = [l for l in field.value.split('\n') if user.mention not in l and "なし" not in l]
            if field.name == target: lines.append(f"• {user.mention}")
            val = '\n'.join(lines) if lines else "なし"
            new_fields.append((field.name, val))
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
        new_embed.set_footer(text=embed.footer.text); new_embed.timestamp = embed.timestamp
        for n, v in new_fields: new_embed.add_field(name=n, value=v)
        await i.response.edit_message(embed=new_embed)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, custom_id="sch_join")
    async def join(self, i, b): await self.update(i, "参加")
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger, custom_id="sch_leave")
    async def leave(self, i, b): await self.update(i, "不参加")

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.danger, custom_id="tk_close")
    async def close(self, i, b):
        await i.response.send_message("ほな閉じるで〜")
        await asyncio.sleep(3)
        await i.channel.delete()

class TicketCreateView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="問い合わせ", style=discord.ButtonStyle.primary, emoji="📩", custom_id="tk_create")
    async def create(self, i, b):
        overwrites = {i.guild.default_role: discord.PermissionOverwrite(read_messages=False), i.user: discord.PermissionOverwrite(read_messages=True), i.guild.me: discord.PermissionOverwrite(read_messages=True)}
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}", overwrites=overwrites)
        await i.response.send_message(f"個別の部屋を作ったで！こっちや: {ch.mention}", ephemeral=True)
        await ch.send(f"{i.user.mention} ここは他の人には見えへんから、安心して要件を書いてな。", view=TicketCloseView())

class ExpressionRegulationAnalyzer:
    def __init__(self): self.config = BotConfig()
    def detect_regulation_question(self, message: str) -> bool:
        has_regulation = any(k in message for k in self.config.REGULATION_KEYWORDS)
        has_question = any(k in message for k in self.config.QUESTION_KEYWORDS)
        question_patterns = [r'.*？$', r'.*\?$', r'^.*ですか.*', r'^.*やろか.*', r'^.*かな.*']
        return has_regulation and (has_question or any(re.search(p, message) for p in question_patterns))
    def extract_regulation_target(self, message: str) -> str:
        patterns = [r'([^。！？\n]+?)への?(?:表現)?規制', r'([^。！？\n]+?)を?規制', r'([^。！？\n]+?)について.*規制']
        for pattern in patterns:
            m = re.search(pattern, message)
            if m: return m.group(1).strip()
        return "対象の表現"
    def create_analysis_prompt(self, question: str, target: str) -> str:
        return f"あなたは「表自派茜（ひょうじは あかね）」です。\n規制対象: {target}\n質問: {question}\n厳格審査基準で分析してください。"

class AiLogic:
    def __init__(self): self.config = BotConfig()
    
    async def call_gpt(self, system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
        model = self.config.GPT_MODEL
        is_reasoning = "gpt-5" in model or "o1" in model
        
        try:
            params = {"model": model, "messages": [{"role":"system","content":system_prompt}, {"role":"user","content":user_message}]}
            
            if is_reasoning:
                params["max_completion_tokens"] = max_tokens
                params["reasoning_effort"] = "medium" 
            else:
                params["max_tokens"] = max_tokens
                params["temperature"] = 0.7
            
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: client.chat.completions.create(**params))
            return resp.choices[0].message.content
            
        except Exception as e:
            logger.error(f"GPT Error: {e}")
            return "ごめん、AIの調子が悪くて返事できへんかった... ちょっと待ってからまた話しかけてな！"

    async def translate(self, text: str, target_lang: str) -> str:
        prompt = f"Translate to {target_lang}. Output ONLY translated text."
        return await self.call_gpt(prompt, text, max_tokens=1000)

    # ★追加: 辞書機能用メソッド
    async def dictionary(self, word: str) -> str:
        prompt = f"あなたは親切な辞書です。「{word}」という言葉の意味を、200文字程度で分かりやすく要約して解説してください。"
        return await self.call_gpt(prompt, word, max_tokens=500)

# ==============================================================================
# 3. Bot本体 & タスク
# ==============================================================================
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=['!', '！'], intents=intents, help_command=None)
        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DB_NAME)
        self.analyzer = ExpressionRegulationAnalyzer()
        self.spam_tracker = defaultdict(lambda: deque(maxlen=5))

    async def setup_hook(self):
        await self.db.init_database()
        self.reminder_task.start()
        self.monthly_rule_task.start()
        self.add_view(ScheduleView())
        self.add_view(TicketCreateView())
        self.add_view(TicketCloseView())

    async def on_ready(self):
        logger.info(f'茜ちゃん(Final V12) 起動！ {self.user}')
        await self.tree.sync()

    @tasks.loop(time=time(hour=7, minute=0, tzinfo=JST))
    async def monthly_rule_task(self):
        now = datetime.now(JST)
        if now.day != 1: return
        logger.info("Running monthly rule task...")
        settings = await self.db.get_all_monthly_settings()
        for guild_id, rule_ch_id, target_ch_id in settings:
            guild = self.get_guild(guild_id)
            if not guild: continue
            rule_ch = guild.get_channel(rule_ch_id)
            target_ch = guild.get_channel(target_ch_id)
            if rule_ch and target_ch:
                msg = f"表現の自由界隈のみなさん、おはようさんやで〜！✨ (๑˃̵ᴗ˂̵)و/n新しい1ヶ月がまた始まったな〜！🔥/nこれがサーバーのルールブックになっとるさかい、/nまだ読んでへん人はこの機会にサッと目を通しといてな📘✨/nほな、今月もよろしゅう頼むで〜！🙏💛\n\n📌 **ルールブック:** {rule_ch.mention}"
                try: await target_ch.send(msg)
                except: pass

    @tasks.loop(seconds=60)
    async def reminder_task(self):
        reminders = await self.db.check_reminders()
        for r in reminders:
            ch = self.get_channel(r[2])
            if ch: await ch.send(f"🔔 <@{r[1]}> リマインダー: **{r[3]}** の時間やで！")

    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        if await self.check_moderation(message): return
        
        auto_res = await self.db.get_auto_reply(message.guild.id, message.content)
        if auto_res: await message.channel.send(auto_res); return

        if self.user in message.mentions: await self.handle_chat(message)
        
        _, _, is_up = await self.db.add_xp(message.author.id, 10)
        if is_up: await message.channel.send(f"🎉 {message.author.mention} レベルアップしたで！")
        
        await self.process_commands(message)

    async def check_moderation(self, message):
        if message.author.guild_permissions.administrator: return False
        if re.search(r'(discord\.gg|discord\.com\/invite)\/', message.content):
            await message.delete()
            await message.channel.send(f"{message.author.mention} 宣伝は禁止やで！", delete_after=5)
            return True
        return False

    async def handle_chat(self, message):
        content = re.sub(r'<@!?\d+>', '', message.content).strip()
        if not content: return
        if not await self.db.check_usage(str(message.author.id)):
            await message.reply("今日の会話回数は終わりや。")
            return
        async with message.channel.typing():
            is_reg = self.analyzer.detect_regulation_question(content)
            if is_reg:
                prompt = self.analyzer.create_analysis_prompt(content, self.analyzer.extract_regulation_target(content))
                resp = await ai_logic.call_gpt(prompt, content, max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS)
            else:
                prompt = f"あなたは「表自派茜（ひょうじは あかね）」です。ユーザー({message.author.display_name})と楽しく会話してください。"
                resp = await ai_logic.call_gpt(prompt, content, max_tokens=self.config.NORMAL_CHAT_MAX_TOKENS)
            
            if len(resp) > 1900:
                file = discord.File(io.BytesIO(resp.encode()), filename="reply.txt")
                await message.reply("長くなったからファイルにするな！", file=file)
            else:
                if is_reg: await message.reply(embed=discord.Embed(title="分析結果", description=resp, color=discord.Color.gold()))
                else: await message.reply(resp)

    async def on_reaction_add(self, reaction, user):
        if user.bot: return
        emoji = str(reaction.emoji)
        if emoji in self.config.FLAG_MAPPING:
            lang = self.config.FLAG_MAPPING[emoji]
            content = reaction.message.content
            if content:
                trans = await ai_logic.translate(content, lang)
                embed = discord.Embed(title=f"🌐 翻訳 ({lang})", description=trans, color=discord.Color.blue())
                embed.add_field(name="原文", value=content[:500], inline=False)
                try: await user.send(embed=embed)
                except: await reaction.message.channel.send(f"{user.mention} DM送れんかったわ。", delete_after=5)

    async def on_raw_reaction_add(self, payload):
        if payload.member.bot: return
        emoji = str(payload.emoji)
        
        # 1. リアクションロール
        rid = await self.db.get_reaction_role(payload.message_id, emoji)
        if rid:
            role = self.get_guild(payload.guild_id).get_role(rid)
            if role: await payload.member.add_roles(role)

        # 2. 殿堂入り (❤️ 10個)
        if emoji == "❤️":
            channel = self.get_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
            reaction = discord.utils.get(msg.reactions, emoji="❤️")
            
            if reaction and reaction.count >= 10:
                if not await self.db.is_starboard_posted(msg.id):
                    sb_channel_id = await self.db.get_channel_setting(payload.guild_id, "starboard_channel_id")
                    if sb_channel_id:
                        sb_ch = self.get_channel(sb_channel_id)
                        if sb_ch:
                            embed = discord.Embed(description=msg.content, color=discord.Color.red(), timestamp=msg.created_at)
                            embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
                            embed.add_field(name="元のメッセージ", value=f"[こちらをタップ]({msg.jump_url})")
                            if msg.attachments:
                                embed.set_image(url=msg.attachments[0].url)
                            
                            await sb_ch.send(content="いいねがたくさん。殿堂入りやね！（茜）", embed=embed)
                            await self.db.add_starboard_log(msg.id)
    
    async def on_raw_reaction_remove(self, payload):
        rid = await self.db.get_reaction_role(payload.message_id, str(payload.emoji))
        if rid:
            guild = self.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(rid)
            if member and role: await member.remove_roles(role)

    async def on_member_join(self, member):
        wid = await self.db.get_channel_setting(member.guild.id, "welcome_channel_id")
        if wid:
            ch = member.guild.get_channel(wid)
            if ch: await ch.send(f"{member.mention} 表現の自由界隈サーバーへようこそ。このサーバーのマスコットキャラクターの表自派茜（ひょうじは あかね）やで！ ゆっくりしていってな！")

bot = AkaneBot()
ai_logic = AiLogic()

# ==============================================================================
# 4. コマンド群
# ==============================================================================

# --- AI ---
@bot.tree.command(name="translate", description="AI翻訳")
async def translate(interaction: discord.Interaction, text: str, language: str = "Japanese"):
    await interaction.response.defer()
    res = await ai_logic.translate(text, language)
    await interaction.followup.send(embed=discord.Embed(title=f"翻訳 ({language})", description=res, color=discord.Color.blue()))

# ★追加: AI辞書機能
@bot.tree.command(name="dictionary", description="AI辞書: 言葉の意味を200文字で解説")
async def dictionary(interaction: discord.Interaction, word: str):
    await interaction.response.defer()
    result = await ai_logic.dictionary(word)
    embed = discord.Embed(title=f"📖 辞書: {word}", description=result, color=discord.Color.green())
    embed.set_footer(text="Powered by AI Dictionary")
    await interaction.followup.send(embed=embed)

# --- コミュニティ ---
@bot.tree.command(name="poll", description="投票を作成")
@app_commands.describe(question="質問内容", option1="選択肢1", option2="選択肢2", option3="選択肢3", option4="選択肢4")
async def poll(interaction: discord.Interaction, question: str, option1: str, option2: str, option3: Optional[str] = None, option4: Optional[str] = None):
    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4)
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    desc = ""
    for i, opt in enumerate(options): desc += f"{emojis[i]} {opt}\n"
    content = f"📊 **{question}** #投票"
    embed = discord.Embed(description=desc, color=discord.Color.gold())
    embed.set_footer(text=f"作成者: {interaction.user.display_name}")
    await interaction.response.send_message(content, embed=embed)
    message = await interaction.original_response()
    for i in range(len(options)): await message.add_reaction(emojis[i])

@bot.tree.command(name="rr_add", description="[管理者] リアクションロール作成")
@app_commands.checks.has_permissions(administrator=True)
async def rr_add(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    try:
        mid = int(message_id)
        msg = await interaction.channel.fetch_message(mid)
        await msg.add_reaction(emoji)
        await bot.db.add_reaction_role(mid, emoji, role.id)
        await interaction.response.send_message(f"設定完了: {emoji} -> {role.name}", ephemeral=True)
    except: await interaction.response.send_message("失敗。IDを確認してな。", ephemeral=True)

@bot.tree.command(name="level_reward", description="[管理者] レベル報酬")
@app_commands.checks.has_permissions(administrator=True)
async def level_reward(interaction: discord.Interaction, level: int, role: discord.Role):
    async with aiosqlite.connect(bot.config.DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)", (interaction.guild.id, level, role.id))
        await db.commit()
    await interaction.response.send_message(f"Lv.{level} で {role.name} 付与設定完了。", ephemeral=True)

# --- ユーティリティ ---
@bot.tree.command(name="schedule", description="スケジュール作成")
async def schedule(interaction: discord.Interaction, title: str, date: str, time: str):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        ts = int(dt.timestamp())
        embed = discord.Embed(title=f"📅 {title}", description=f"日時: <t:{ts}:F>", color=discord.Color.green())
        embed.add_field(name="参加", value="なし"); embed.add_field(name="不参加", value="なし")
        await interaction.response.send_message(embed=embed, view=ScheduleView())
        try: await interaction.guild.create_scheduled_event(name=title, start_time=dt, end_time=dt+timedelta(hours=2), location="Discord", entity_type=discord.EntityType.external, privacy_level=discord.PrivacyLevel.guild_only)
        except: pass
    except: await interaction.response.send_message("日時は `YYYY/MM/DD` `HH:MM` でな！", ephemeral=True)

@bot.tree.command(name="search", description="メッセージ検索")
async def search(interaction: discord.Interaction, keyword: str):
    await interaction.response.defer(ephemeral=True)
    found = []
    async for m in interaction.channel.history(limit=500):
        if keyword in m.content: found.append(m)
        if len(found) >= 10: break
    text = "\n".join([f"• [{m.content[:20]}]({m.jump_url})" for m in found]) if found else "なし"
    await interaction.followup.send(embed=discord.Embed(title=f"検索: {keyword}", description=text), ephemeral=True)

@bot.tree.command(name="remind", description="リマインダー")
async def remind(interaction: discord.Interaction, minutes: int, message: str):
    await bot.db.add_reminder(interaction.user.id, interaction.channel_id, message, minutes)
    await interaction.response.send_message(f"{minutes}分後に通知するで。", ephemeral=True)

@bot.tree.command(name="auto_reply_add", description="[管理者] 自動応答追加")
@app_commands.checks.has_permissions(administrator=True)
async def auto_reply_add(interaction: discord.Interaction, trigger: str, response: str):
    await bot.db.add_auto_reply(interaction.guild.id, trigger, response)
    await interaction.response.send_message(f"設定完了: {trigger} -> {response}", ephemeral=True)

# --- 管理・ログ ---
@bot.tree.command(name="ng_add", description="[管理者] NGワード追加")
@app_commands.checks.has_permissions(administrator=True)
async def ng_add(interaction: discord.Interaction, word: str):
    await bot.db.add_ng_word(interaction.guild.id, word)
    await interaction.response.send_message(f"NGワード「{word}」追加。", ephemeral=True)

@bot.tree.command(name="setup_monthly_rule", description="[管理者] 毎月1日のルール周知を設定")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(rule_channel="ルールブックのチャンネル", target_channel="投稿先の雑談チャンネル")
async def setup_monthly_rule(interaction: discord.Interaction, rule_channel: discord.TextChannel, target_channel: discord.TextChannel):
    await bot.db.set_monthly_rule(interaction.guild.id, rule_channel.id, target_channel.id)
    await interaction.response.send_message(f"✅ 設定完了！", ephemeral=True)

@bot.tree.command(name="set_welcome", description="[管理者] 挨拶チャンネル設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "welcome_channel_id", channel.id)
    await interaction.response.send_message(f"挨拶場所: {channel.mention}", ephemeral=True)

@bot.tree.command(name="set_log", description="[管理者] 監査ログ設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_log(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "log_channel_id", channel.id)
    await interaction.response.send_message(f"ログ場所: {channel.mention}", ephemeral=True)

@bot.tree.command(name="setup_starboard", description="[管理者] 殿堂入り(Starboard)設定 (❤️10個で転送)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_starboard(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "starboard_channel_id", channel.id)
    await interaction.response.send_message(f"殿堂入り先を {channel.mention} に設定したで！(❤️10個で転送)", ephemeral=True)

@bot.tree.command(name="setup_ticket", description="[管理者] チケット設置")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction):
    await interaction.channel.send("📩 サポート窓口", view=TicketCreateView())
    await interaction.response.send_message("完了", ephemeral=True)

@bot.tree.command(name="kick", description="[管理者] Kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member): await member.kick(); await interaction.response.send_message("Kick完了")

@bot.tree.command(name="ban", description="[管理者] Ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member): await member.ban(); await interaction.response.send_message("Ban完了")

@bot.tree.command(name="purge", description="[管理者] 削除")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int): await interaction.channel.purge(limit=amount); await interaction.response.send_message("削除完了", ephemeral=True)

if __name__ == '__main__':
    if DISCORD_TOKEN: bot.run(DISCORD_TOKEN)
