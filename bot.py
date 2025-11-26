import discord
from discord import app_commands, EntityType, PrivacyLevel
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
import io
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
    GPT_MODEL = "gpt-5.1" # エラー回避ロジック適用済み

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

# --- Bot設定 ---
class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    
    if os.path.exists("/data"):
        DB_NAME = '/data/akane_final_v4.db'
    else:
        DB_NAME = 'akane_final_v4.db'

    REGULATION_ANALYSIS_MAX_TOKENS = 2000
    NORMAL_CHAT_MAX_TOKENS = 800
    GPT_MODEL = OpenAIConfig.GPT_MODEL

    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '制限', '禁止', '表現の自由', '言論統制', '弾圧']
    QUESTION_KEYWORDS = ['妥当', '適切', '正しい', 'どう思う', '判断', '評価', '分析']

    # 国旗と言語のマッピング
    FLAG_MAPPING = {
        "🇺🇸": "English", "🇬🇧": "English", "🇨🇦": "English",
        "🇯🇵": "Japanese", "🇨🇳": "Chinese", "🇰🇷": "Korean",
        "🇫🇷": "French", "🇩🇪": "German", "🇮🇹": "Italian",
        "🇪🇸": "Spanish", "🇷🇺": "Russian", "🇻🇳": "Vietnamese",
        "🇹🇭": "Thai", "🇮🇩": "Indonesian"
    }

# ==============================================================================
# 5. システム・仕様 (データベース & Botコア)
# ==============================================================================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # ログ・履歴系
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, count INTEGER DEFAULT 0, UNIQUE(user_id, date))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, autorole_id INTEGER, welcome_channel_id INTEGER, log_channel_id INTEGER)''')
            # ユーザーデータ
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, message TEXT, end_time TEXT)''')
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    # --- 設定保存用 ---
    async def set_log_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", (guild_id,))
            if await cursor.fetchone():
                await db.execute("UPDATE settings SET log_channel_id = ? WHERE guild_id = ?", (channel_id, guild_id))
            else:
                await db.execute("INSERT INTO settings (guild_id, log_channel_id) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def get_log_channel(self, guild_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT log_channel_id FROM settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_welcome_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", (guild_id,))
            if await cursor.fetchone():
                await db.execute("UPDATE settings SET welcome_channel_id = ? WHERE guild_id = ?", (channel_id, guild_id))
            else:
                await db.execute("INSERT INTO settings (guild_id, welcome_channel_id) VALUES (?, ?)", (guild_id, channel_id))
            await db.commit()

    async def get_welcome_channel(self, guild_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("SELECT welcome_channel_id FROM settings WHERE guild_id = ?", (guild_id,))
            row = await cursor.fetchone()
            return row[0] if row else None

    # --- ユーザーデータ系 ---
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

    async def add_reminder(self, user_id: int, channel_id: int, message: str, minutes: int):
        end_time = (datetime.now(JST) + timedelta(minutes=minutes)).isoformat()
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("INSERT INTO reminders (user_id, channel_id, message, end_time) VALUES (?, ?, ?, ?)", (user_id, channel_id, message, end_time))
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

# --- GPTロジッククラス ---
class AiLogic:
    def __init__(self): self.config = BotConfig()

    async def call_gpt(self, system_prompt: str, user_message: str, max_tokens: int = 500) -> str:
        model = self.config.GPT_MODEL
        is_reasoning = "gpt-5" in model or "o1" in model
        try:
            params = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
            }
            if is_reasoning:
                params["max_completion_tokens"] = max_tokens
                params["reasoning_effort"] = "medium"
            else:
                params["max_tokens"] = max_tokens
                params["temperature"] = 0.7

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: client.chat.completions.create(**params))
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GPT Error: {e}")
            return "APIエラーが発生しました。"

    async def translate(self, text: str, target_lang: str) -> str:
        prompt = f"Translate the following text into {target_lang}. Output ONLY the translated text."
        return await self.call_gpt(prompt, text, max_tokens=1000)

ai_logic = AiLogic()

# --- Bot本体クラス ---
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=['!', '！'], intents=intents, help_command=None)
        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DB_NAME)

    async def setup_hook(self):
        await self.db.init_database()
        self.reminder_task.start()
        self.add_view(ScheduleView())
        self.add_view(TicketCreateView())

    @tasks.loop(seconds=60)
    async def reminder_task(self):
        reminders = await self.db.check_reminders()
        for r in reminders:
            ch = self.get_channel(r[2])
            if ch: await ch.send(f"🔔 <@{r[1]}> リマインダー: **{r[3]}** の時間やで！")

    async def on_ready(self):
        logger.info(f'茜ちゃん(Final V4 Sorted) 起動！ {self.user}')
        await self.tree.sync()

    # ==============================================================================
    # 1. AI・インテリジェンス機能 (イベント処理)
    # ==============================================================================
    
    # ★国旗リアクション翻訳
    async def on_reaction_add(self, reaction, user):
        if user.bot: return
        emoji = str(reaction.emoji)
        if emoji in self.config.FLAG_MAPPING:
            target_lang = self.config.FLAG_MAPPING[emoji]
            message_content = reaction.message.content
            if not message_content: return
            
            translated_text = await ai_logic.translate(message_content, target_lang)
            
            embed = discord.Embed(title=f"🌐 翻訳結果 ({target_lang})", color=discord.Color.blue())
            embed.add_field(name="原文", value=message_content[:500] + ("..." if len(message_content) > 500 else ""), inline=False)
            embed.add_field(name="翻訳", value=translated_text[:1024], inline=False)
            embed.set_footer(text="このメッセージは君にしか見えてないで！")
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                await reaction.message.channel.send(f"{user.mention} DM送れへんかったわ💦", delete_after=5)

    # ★会話 & XP獲得トリガー
    async def on_message(self, message):
        if message.author.bot: return
        
        # AI会話 (メンション or DM)
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat(message)
        
        # XP加算 (コミュニティ機能)
        if message.guild:
            _, _, is_up = await self.db.add_xp(message.author.id, 10)
            if is_up: await message.channel.send(f"🎉 {message.author.mention} レベルアップしたで！")
        
        await self.process_commands(message)

    async def handle_chat(self, message):
        content = re.sub(r'<@!?\d+>', '', message.content).strip()
        if not content: return
        if not await self.db.check_usage(str(message.author.id)):
            await message.reply("今日の会話回数は終わりや。また明日な！")
            return

        async with message.channel.typing():
            is_reg = any(k in content for k in self.config.REGULATION_KEYWORDS)
            if is_reg:
                prompt = f"あなたは「表自派茜」です。以下のトピックについて憲法学的観点から詳細に分析してください。\n{content}"
                resp = await ai_logic.call_gpt(prompt, content, max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS)
            else:
                prompt = f"あなたは「表自派茜」という関西弁の女子高生です。ユーザー({message.author.display_name})と楽しく会話してください。"
                resp = await ai_logic.call_gpt(prompt, content)
            
            # 長文時のファイル出力
            if len(resp) > 1900:
                buffer = io.BytesIO(resp.encode('utf-8'))
                file = discord.File(buffer, filename="analysis_result.txt")
                await message.reply("話が長くなりすぎたから、ファイルにまとめたで！読んでな📄", file=file)
            else:
                if is_reg:
                    embed = discord.Embed(title="📋 茜の分析", description=resp, color=discord.Color.gold())
                    await message.reply(embed=embed)
                else:
                    await message.reply(resp)

    # ==============================================================================
    # 3. コミュニティ活性化 (イベント処理)
    # ==============================================================================
    
    # ★自動ウェルカムメッセージ
    async def on_member_join(self, member):
        welcome_ch_id = await self.db.get_welcome_channel(member.guild.id)
        if welcome_ch_id:
            channel = member.guild.get_channel(welcome_ch_id)
            if channel:
                msg = f"{member.mention} 表現の自由界隈サーバーへようこそ。このサーバーのマスコットキャラクターの表自派茜やで！ ゆっくりしていってな！"
                await channel.send(msg)

    # ==============================================================================
    # 4. サーバー管理・治安維持 (イベント処理)
    # ==============================================================================
    
    # ★監査ログ (メッセージ削除検知)
    async def on_message_delete(self, message):
        if message.author.bot: return
        log_ch_id = await self.db.get_log_channel(message.guild.id)
        if log_ch_id:
            ch = message.guild.get_channel(log_ch_id)
            if ch:
                embed = discord.Embed(title="🗑️ メッセージ削除", color=discord.Color.red(), timestamp=datetime.now())
                embed.add_field(name="送信者", value=message.author.mention, inline=True)
                embed.add_field(name="内容", value=message.content or "(画像)", inline=False)
                await ch.send(embed=embed)

bot = AkaneBot()

# ==============================================================================
# 1. AI・インテリジェンス機能 (コマンド)
# ==============================================================================

@bot.tree.command(name="translate", description="AI翻訳: 指定した言語に翻訳します")
async def translate(interaction: discord.Interaction, text: str, language: str = "Japanese"):
    await interaction.response.defer()
    result = await ai_logic.translate(text, language)
    embed = discord.Embed(title="🌐 翻訳結果", color=discord.Color.blue())
    embed.add_field(name="原文", value=text[:1024], inline=False)
    embed.add_field(name=f"翻訳 ({language})", value=result[:1024], inline=False)
    await interaction.followup.send(embed=embed)

# ==============================================================================
# 2. ユーティリティ (便利ツール)
# ==============================================================================

# --- スケジュール作成 ---
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
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger, custom_id="sch_lv")
    async def leave(self, i, b): await self.update(i, "不参加")

@bot.tree.command(name="schedule", description="スケジュール作成＆サーバーイベント登録")
async def schedule(interaction: discord.Interaction, title: str, date: str, time: str, description: str = "詳細はスレッドにて"):
    try:
        start_str = f"{date} {time}"
        start_dt = datetime.strptime(start_str, "%Y/%m/%d %H:%M").replace(tzinfo=JST)
        end_dt = start_dt + timedelta(hours=2)
        ts = int(start_dt.timestamp())
        embed = discord.Embed(title=f"📅 {title}", description=f"日時: <t:{ts}:F>\n{description}", color=discord.Color.green())
        for s in ["参加", "不参加"]: embed.add_field(name=f"【{s}】", value="なし")
        embed.set_footer(text=f"作成者: {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed, view=ScheduleView())
        
        try:
            await interaction.guild.create_scheduled_event(
                name=title, start_time=start_dt, end_time=end_dt, description=description,
                location="Discord内", entity_type=discord.EntityType.external, privacy_level=discord.PrivacyLevel.guild_only
            )
            await interaction.followup.send("✅ イベントにも登録したで！", ephemeral=True)
        except:
            await interaction.followup.send("⚠️ イベント登録は権限不足で失敗したかも。", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("日時は `YYYY/MM/DD` `HH:MM` でな！", ephemeral=True)

# --- メッセージ検索 ---
@bot.tree.command(name="search", description="メッセージ検索 (直近1000件)")
async def search(interaction: discord.Interaction, keyword: str, member: Optional[discord.Member] = None, channel: Optional[discord.TextChannel] = None):
    await interaction.response.defer(ephemeral=True)
    target = channel if channel else interaction.channel
    found = []
    async for msg in target.history(limit=1000):
        if msg.author.bot: continue
        if member and msg.author != member: continue
        if keyword in msg.content:
            found.append(msg)
            if len(found) >= 10: break
    
    if not found:
        await interaction.followup.send("見つからへんかったわ...", ephemeral=True)
        return
    
    text = f"🔍 **検索結果** ({keyword})\n\n"
    for m in found:
        c = m.content[:30] + "..." if len(m.content) > 30 else m.content
        text += f"• [{c}]({m.jump_url}) - {m.author.mention} ({m.created_at.strftime('%m/%d')})\n"
    await interaction.followup.send(embed=discord.Embed(description=text, color=discord.Color.blue()), ephemeral=True)

# --- リマインダー ---
@bot.tree.command(name="remind", description="リマインダー設定")
async def remind(interaction: discord.Interaction, minutes: int, message: str):
    await bot.db.add_reminder(interaction.user.id, interaction.channel_id, message, minutes)
    await interaction.response.send_message(f"了解！ {minutes}分後に通知するな。", ephemeral=True)

# --- サポートチケット (Viewは4.管理者機能のsetupで利用) ---
class TicketCreateView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="問い合わせ", style=discord.ButtonStyle.primary, emoji="📩", custom_id="tk_cr")
    async def create(self, i, b):
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}")
        await i.response.send_message(f"作成したで: {ch.mention}", ephemeral=True)
        await ch.send(f"{i.user.mention} どうぞ", view=TicketCloseView())

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.danger)
    async def close(self, i, b): await i.response.send_message("ほなな"); await asyncio.sleep(3); await i.channel.delete()

# ==============================================================================
# 4. サーバー管理・治安維持 (管理者専用コマンド)
# ==============================================================================

@bot.tree.command(name="set_welcome", description="[管理者] 入室時の挨拶メッセージを流すチャンネルを設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_welcome_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"おけ！これからは {channel.mention} で挨拶するな！", ephemeral=True)

@bot.tree.command(name="set_log", description="[管理者] 監査ログ設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_log(interaction: discord.Interaction, channel: discord.TextChannel):
    await bot.db.set_log_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"監査ログを {channel.mention} に設定したで！", ephemeral=True)

@bot.tree.command(name="kick", description="[管理者] メンバーをKick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "なし"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} をKickしたで。(理由: {reason})", ephemeral=True)

@bot.tree.command(name="ban", description="[管理者] メンバーをBan")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "なし"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} をBanしたで。(理由: {reason})", ephemeral=True)

@bot.tree.command(name="purge", description="[管理者] メッセージを一括削除")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(amount="削除件数", member="特定の人のみ", hours="○時間以内のみ")
async def purge(interaction: discord.Interaction, amount: int, member: Optional[discord.Member] = None, hours: Optional[int] = None):
    await interaction.response.defer(ephemeral=True)
    def check(msg):
        if member and msg.author != member: return False
        if hours:
            cutoff = datetime.now(msg.created_at.tzinfo) - timedelta(hours=hours)
            if msg.created_at < cutoff: return False
        return True
    deleted = await interaction.channel.purge(limit=amount, check=check)
    msg = f"{len(deleted)}件"
    if member: msg += f" ({member.display_name})"
    if hours: msg += f" ({hours}時間以内)"
    await interaction.followup.send(f"🗑️ {msg} 削除したで！", ephemeral=True)

@bot.tree.command(name="setup_ticket", description="[管理者] チケット設置")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction):
    await interaction.channel.send("📩 サポート窓口", view=TicketCreateView())
    await interaction.response.send_message("完了", ephemeral=True)

# ==============================================================================
# エントリポイント
# ==============================================================================
if __name__ == '__main__':
    if DISCORD_TOKEN: bot.run(DISCORD_TOKEN)
