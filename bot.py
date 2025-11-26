import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import os
import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
import pytz
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional
from dotenv import load_dotenv

# ==============================================================================
# 0. 環境変数・基本設定
# ==============================================================================
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
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
        DB_NAME = '/data/akane_pro_sorted.db'
    else:
        DB_NAME = 'akane_pro_sorted.db'
        
    # 国旗翻訳用マッピング
    FLAG_MAPPING = {
        "🇺🇸": "English", "🇬🇧": "English", "🇨🇦": "English", "🇯🇵": "Japanese",
        "🇨🇳": "Chinese", "🇰🇷": "Korean", "🇫🇷": "French", "🇩🇪": "German",
        "🇮🇹": "Italian", "🇪🇸": "Spanish", "🇷🇺": "Russian", "🇻🇳": "Vietnamese"
    }
    # 分析トリガー
    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '制限', '禁止', '表現の自由', '言論統制', '弾圧']

# ==============================================================================
# 1. データベース管理 (Database Manager)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # 基本ログ
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, count INTEGER DEFAULT 0, UNIQUE(user_id, date))''')
            # 設定
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, welcome_channel_id INTEGER, log_channel_id INTEGER, starboard_channel_id INTEGER)''')
            # コミュニティ (XP, 報酬, リアクションロール)
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS level_rewards (guild_id INTEGER, level INTEGER, role_id INTEGER, PRIMARY KEY(guild_id, level))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (message_id INTEGER, emoji TEXT, role_id INTEGER)''')
            # ユーティリティ & モデレーション
            await db.execute('''CREATE TABLE IF NOT EXISTS ng_words (guild_id INTEGER, word TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS auto_replies (guild_id INTEGER, trigger TEXT, response TEXT)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, message TEXT, end_time TEXT)''')
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    # --- 汎用設定取得/更新 ---
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

    # --- コミュニティ機能 (XP/RR) ---
    async def add_xp(self, guild: discord.Guild, member: discord.Member, amount: int) -> bool:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (member.id,))
            row = await cursor.fetchone()
            is_levelup = False
            if row:
                xp, level = row
                xp += amount
                if xp >= level * 100:
                    xp = 0; level += 1; is_levelup = True
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, member.id))
            else:
                xp, level = amount, 1
                await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (member.id, xp, level))
            await db.commit()
            
            # レベル報酬ロール付与
            if is_levelup:
                r_cursor = await db.execute("SELECT role_id FROM level_rewards WHERE guild_id = ? AND level <= ?", (guild.id, level))
                rewards = await r_cursor.fetchall()
                for r_row in rewards:
                    role = guild.get_role(r_row[0])
                    if role and role not in member.roles:
                        try: await member.add_roles(role)
                        except: pass
            return is_levelup

    async def add_reaction_role(self, message_id: int, emoji: str, role_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO reaction_roles (message_id, emoji, role_id) VALUES (?, ?, ?)", (message_id, emoji, role_id))
            await db.commit()

    async def get_reaction_role(self, message_id: int, emoji: str):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?", (message_id, emoji))
            row = await cursor.fetchone()
            return row[0] if row else None

    # --- ユーティリティ (Auto-Reply/Remind/Limit) ---
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

    # --- モデレーション (NG) ---
    async def add_ng_word(self, guild_id, word):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO ng_words (guild_id, word) VALUES (?, ?)", (guild_id, word))
            await db.commit()

    async def get_ng_words(self, guild_id):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT word FROM ng_words WHERE guild_id = ?", (guild_id,))
            return [r[0] for r in await cursor.fetchall()]

# ==============================================================================
# 2. Bot本体 & イベントハンドラ
# ==============================================================================
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=['!', '！'], intents=intents, help_command=None)
        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DB_NAME)
        self.spam_tracker = defaultdict(lambda: deque(maxlen=5))

    async def setup_hook(self):
        await self.db.init_database()
        self.reminder_task.start()
        self.add_view(ScheduleView())

    async def on_ready(self):
        logger.info(f'茜ちゃん(Pro Sorted) 起動！ {self.user}')
        await self.tree.sync()

    @tasks.loop(seconds=60)
    async def reminder_task(self):
        reminders = await self.db.check_reminders()
        for r in reminders:
            ch = self.get_channel(r[2])
            if ch: await ch.send(f"🔔 <@{r[1]}> リマインダー: **{r[3]}** の時間やで！")

    # ----------------------------------------------------------------
    # (A) 自動モデレーション処理
    # ----------------------------------------------------------------
    async def check_moderation(self, message):
        if message.author.guild_permissions.administrator: return False
        content = message.content
        guild_id = message.guild.id

        # 招待リンク削除
        if re.search(r'(discord\.gg|discord\.com\/invite)\/', content):
            await message.delete()
            await message.channel.send(f"{message.author.mention} ⚠️ 宣伝は禁止やで！", delete_after=5)
            return True

        # NGワード削除
        ng_words = await self.db.get_ng_words(guild_id)
        for word in ng_words:
            if word in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention} ⚠️ NGワードが含まれてるで！", delete_after=5)
                return True

        # All Caps (大文字叫び) 削除
        if len(content) > 10 and content.isupper():
            eng_chars = len(re.findall(r'[A-Z]', content))
            if eng_chars / len(content) > 0.7:
                await message.delete()
                await message.channel.send(f"{message.author.mention} ⚠️ 大文字で叫ぶのはやめてな！", delete_after=5)
                return True

        # 連投スパム (5秒に5回)
        now = datetime.now().timestamp()
        self.spam_tracker[message.author.id].append(now)
        if len(self.spam_tracker[message.author.id]) == 5:
            timestamps = self.spam_tracker[message.author.id]
            if timestamps[-1] - timestamps[0] < 5:
                try:
                    await message.author.timeout(timedelta(minutes=10), reason="連投スパム")
                    await message.channel.send(f"🚫 {message.author.mention} 連投判定でタイムアウトしたで。")
                except: pass
                return True
        return False

    # ----------------------------------------------------------------
    # (B) メッセージイベント (AI, AutoReply, XP)
    # ----------------------------------------------------------------
    async def on_message(self, message):
        if message.author.bot or not message.guild: return

        # 1. モデレーションチェック
        if await self.check_moderation(message): return

        # 2. 自動応答
        auto_res = await self.db.get_auto_reply(message.guild.id, message.content)
        if auto_res:
            await message.channel.send(auto_res)
            return

        # 3. AIチャット (メンション時)
        if self.user in message.mentions:
            await self.handle_ai_chat(message)

        # 4. XP加算
        is_up = await self.db.add_xp(message.guild, message.author, 10)
        if is_up: await message.channel.send(f"🎉 {message.author.mention} レベルアップしたで！")

        await self.process_commands(message)

    # ----------------------------------------------------------------
    # (C) AIロジック & GPT呼び出し
    # ----------------------------------------------------------------
    async def handle_ai_chat(self, message):
        content = re.sub(r'<@!?\d+>', '', message.content).strip()
        if not content: return
        if not await self.db.check_usage(str(message.author.id)):
            await message.reply("今日の会話回数は終わりや。また明日な！")
            return

        async with message.channel.typing():
            # 性格設定: 表現規制の話題だけ熱くなる
            prompt = (
                "あなたは「表自派茜（ひょうじは あかね）」という元気な関西弁の女子高生AIです。\n"
                "基本的には親しみやすく、友達のように振る舞ってください。\n"
                "ただし、「表現の自由」「規制」「検閲」などの話題が出た場合だけは、"
                "スイッチが入ったようにテンションが上がり、熱く語り出してください。"
            )
            resp = await self.call_gpt(prompt, content)
            await message.reply(resp)

    async def call_gpt(self, system, user):
        is_reasoning = "gpt-5" in OpenAIConfig.GPT_MODEL or "o1" in OpenAIConfig.GPT_MODEL
        try:
            params = {"model": OpenAIConfig.GPT_MODEL, "messages": [{"role":"system","content":system}, {"role":"user","content":user}]}
            if is_reasoning:
                params["max_completion_tokens"] = 800
                params["reasoning_effort"] = "medium"
            else:
                params["max_tokens"] = 800
                params["temperature"] = 0.8
            
            resp = await asyncio.to_thread(client.chat.completions.create, **params)
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT Error: {e}")
            return "あかん、調子悪いわ..."

    # ----------------------------------------------------------------
    # (D) リアクションイベント (RR, Starboard, 翻訳)
    # ----------------------------------------------------------------
    async def on_raw_reaction_add(self, payload):
        if payload.member.bot: return
        
        # リアクションロール
        role_id = await self.db.get_reaction_role(payload.message_id, str(payload.emoji))
        if role_id:
            guild = self.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            if role: await payload.member.add_roles(role)

        # スターボード
        if str(payload.emoji) == "⭐":
            channel = self.get_channel(payload.channel_id)
            msg = await channel.fetch_message(payload.message_id)
            reaction = discord.utils.get(msg.reactions, emoji="⭐")
            if reaction and reaction.count >= 3:
                sb_id = await self.db.get_channel_setting(payload.guild_id, "starboard_channel_id")
                if sb_id:
                    sb_ch = self.get_channel(sb_id)
                    embed = discord.Embed(description=msg.content, color=discord.Color.gold())
                    embed.set_author(name=msg.author.display_name, icon_url=msg.author.display_avatar.url)
                    embed.add_field(name="元の場所", value=f"[Jump]({msg.jump_url})")
                    if msg.attachments: embed.set_image(url=msg.attachments[0].url)
                    await sb_ch.send(content=f"⭐ **{reaction.count}** {channel.mention}", embed=embed)

    async def on_raw_reaction_remove(self, payload):
        # リアクションロール解除
        role_id = await self.db.get_reaction_role(payload.message_id, str(payload.emoji))
        if role_id:
            guild = self.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            role = guild.get_role(role_id)
            if member and role: await member.remove_roles(role)

    # 国旗翻訳 (DM送信)
    async def on_reaction_add(self, reaction, user):
        if user.bot: return
        emoji = str(reaction.emoji)
        if emoji in self.config.FLAG_MAPPING:
            lang = self.config.FLAG_MAPPING[emoji]
            content = reaction.message.content
            if not content: return
            
            # 簡易翻訳呼び出し
            prompt = f"Translate to {lang}: {content}"
            translated = await self.call_gpt(prompt, content)
            
            embed = discord.Embed(title=f"🌐 翻訳結果 ({lang})", color=discord.Color.blue())
            embed.add_field(name="原文", value=content[:500], inline=False)
            embed.add_field(name="翻訳", value=translated[:1024], inline=False)
            try: await user.send(embed=embed)
            except: await reaction.message.channel.send(f"{user.mention} DM送れへんかったわ💦", delete_after=5)

    # ----------------------------------------------------------------
    # (E) 管理ログ & Welcomeイベント
    # ----------------------------------------------------------------
    async def send_log(self, guild, title, desc, color):
        log_id = await self.db.get_channel_setting(guild.id, "log_channel_id")
        if log_id:
            ch = guild.get_channel(log_id)
            if ch:
                embed = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.now())
                await ch.send(embed=embed)

    async def on_message_delete(self, message):
        if message.author.bot: return
        await self.send_log(message.guild, "🗑️ メッセージ削除", f"**User:** {message.author.mention}\n**Ch:** {message.channel.mention}\n**Content:** {message.content}", discord.Color.red())

    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            desc = ""
            if not before.channel: desc = f"📥 **参加:** {after.channel.name}"
            elif not after.channel: desc = f"📤 **退出:** {before.channel.name}"
            else: desc = f"➡️ **移動:** {before.channel.name} → {after.channel.name}"
            await self.send_log(member.guild, "🔊 ボイスログ", f"{member.mention} {desc}", discord.Color.green())

    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            await self.send_log(before.guild, "👤 名前変更", f"{before.name}: {before.nick} -> {after.nick}", discord.Color.blue())
        if before.roles != after.roles:
            await self.send_log(before.guild, "🛡️ ロール変更", f"{before.mention} のロールが変わったで", discord.Color.blue())

    async def on_member_join(self, member):
        wc_id = await self.db.get_channel_setting(member.guild.id, "welcome_channel_id")
        if wc_id:
            ch = member.guild.get_channel(wc_id)
            if ch: await ch.send(f"{member.mention} 表現の自由界隈サーバーへようこそ。このサーバーのマスコットキャラクターの表自派茜（ひょうじは あかね）やで！ ゆっくりしていってな！")

bot = AkaneBot()

# ==============================================================================
# 3. スラッシュコマンド群 (カテゴリ別)
# ==============================================================================

# --- A. 設定 (Setup) ---
@bot.tree.command(name="setup_log", description="[管理者] 監査ログ設定")
@app_commands.checks.has_permissions(administrator=True)
async def setup_log(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "log_channel_id", channel.id)
    await interaction.response.send_message(f"監査ログを {channel.mention} にしたで！")

@bot.tree.command(name="setup_welcome", description="[管理者] 挨拶チャンネル設定")
@app_commands.checks.has_permissions(administrator=True)
async def setup_welcome(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "welcome_channel_id", channel.id)
    await interaction.response.send_message(f"挨拶を {channel.mention} にしたで！")

@bot.tree.command(name="setup_starboard", description="[管理者] スターボード設定 (⭐3つで転送)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_starboard(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_channel_setting(interaction.guild.id, "starboard_channel_id", channel.id)
    await interaction.response.send_message(f"スターボードを {channel.mention} にしたで！")

# --- B. コミュニティ管理 (XP/RR) ---
@bot.tree.command(name="rr_add", description="[管理者] リアクションロール作成")
@app_commands.checks.has_permissions(administrator=True)
async def rr_add(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    try:
        mid = int(message_id)
        msg = await interaction.channel.fetch_message(mid)
        await msg.add_reaction(emoji)
        await bot.db.add_reaction_role(mid, emoji, role.id)
        await interaction.response.send_message(f"設定完了！ {emoji} で {role.name} 付与や！")
    except: await interaction.response.send_message("失敗。IDか権限を確認してな。", ephemeral=True)

@bot.tree.command(name="level_reward", description="[管理者] レベル報酬ロール設定")
@app_commands.checks.has_permissions(administrator=True)
async def level_reward(interaction: discord.Interaction, level: int, role: discord.Role):
    async with aiosqlite.connect(bot.config.DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)", (interaction.guild.id, level, role.id))
        await db.commit()
    await interaction.response.send_message(f"Lv.{level} で {role.name} をあげるで！")

# --- C. 自動モデレーション & 応答設定 ---
@bot.tree.command(name="ng_add", description="[管理者] NGワード追加")
@app_commands.checks.has_permissions(administrator=True)
async def ng_add(interaction: discord.Interaction, word: str):
    await bot.db.add_ng_word(interaction.guild.id, word)
    await interaction.response.send_message(f"NGワード「{word}」追加完了。", ephemeral=True)

@bot.tree.command(name="auto_reply_add", description="[管理者] 自動応答追加")
@app_commands.checks.has_permissions(administrator=True)
async def auto_reply_add(interaction: discord.Interaction, trigger: str, response: str):
    await bot.db.add_auto_reply(interaction.guild.id, trigger, response)
    await interaction.response.send_message(f"「{trigger}」に「{response}」って返すわ！", ephemeral=True)

# --- D. ユーティリティ (Schedule/Remind/Search/Translate) ---
@bot.tree.command(name="schedule", description="スケジュール作成")
async def schedule(interaction: discord.Interaction, title: str, date: str, time: str):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        ts = int(dt.timestamp())
        embed = discord.Embed(title=f"📅 {title}", description=f"日時: <t:{ts}:F>", color=discord.Color.green())
        embed.set_footer(text=f"作成者: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ScheduleView())
        try:
            await interaction.guild.create_scheduled_event(name=title, start_time=dt, end_time=dt+timedelta(hours=2), location="Discord", entity_type=discord.EntityType.external, privacy_level=discord.PrivacyLevel.guild_only)
        except: pass
    except: await interaction.response.send_message("日時は `YYYY/MM/DD` `HH:MM` でな！", ephemeral=True)

class ScheduleView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="参加", style=discord.ButtonStyle.success)
    async def join(self, i, b): await i.response.send_message("参加やな！", ephemeral=True)
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger)
    async def leave(self, i, b): await i.response.send_message("不参加か…", ephemeral=True)

@bot.tree.command(name="remind", description="リマインダー")
async def remind(interaction: discord.Interaction, minutes: int, message: str):
    await bot.db.add_reminder(interaction.user.id, interaction.channel_id, message, minutes)
    await interaction.response.send_message(f"{minutes}分後に通知するな。", ephemeral=True)

@bot.tree.command(name="search", description="メッセージ検索")
async def search(interaction: discord.Interaction, keyword: str, member: Optional[discord.Member]=None):
    await interaction.response.defer(ephemeral=True)
    found = []
    async for m in interaction.channel.history(limit=500):
        if member and m.author != member: continue
        if keyword in m.content: found.append(m)
        if len(found) >= 10: break
    text = "\n".join([f"• [{m.content[:20]}]({m.jump_url})" for m in found]) if found else "なし"
    await interaction.followup.send(embed=discord.Embed(title="検索結果", description=text), ephemeral=True)

@bot.tree.command(name="translate", description="AI翻訳")
async def translate(interaction: discord.Interaction, text: str, language: str = "Japanese"):
    await interaction.response.defer()
    prompt = f"Translate to {language}: {text}"
    resp = await bot.call_gpt(prompt, text)
    await interaction.followup.send(f"**翻訳:** {resp}")

# --- E. 手動モデレーション (Kick/Ban/Purge) ---
@bot.tree.command(name="kick", description="[管理者] Kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member): await member.kick(); await interaction.response.send_message("Kickしたで")

@bot.tree.command(name="ban", description="[管理者] Ban")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member): await member.ban(); await interaction.response.send_message("Banしたで")

@bot.tree.command(name="purge", description="[管理者] メッセージ削除")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int): await interaction.channel.purge(limit=amount); await interaction.response.send_message("削除したで", ephemeral=True)

if __name__ == '__main__':
    if DISCORD_TOKEN: bot.run(DISCORD_TOKEN)
