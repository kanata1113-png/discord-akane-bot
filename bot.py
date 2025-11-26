import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import os
import asyncio
import aiosqlite  # 非同期DBライブラリ推奨
import logging
from datetime import datetime, timedelta
import pytz
import re
from typing import Dict, Optional

# ==========================================
# 0. 設定・ログ準備
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI設定
class OpenAIConfig:
    GPT_MODEL = "gpt-4o" # 現実的に動作する最強モデルを指定

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

# Bot設定
class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    # Railway対応のDBパス
    if os.path.exists("/data"):
        DB_NAME = '/data/ultimate_bot.db'
    else:
        DB_NAME = 'ultimate_bot.db'

    REGULATION_KEYWORDS = ['表現規制', '規制', '検閲', '表現の自由', '言論統制', '弾圧']
    QUESTION_KEYWORDS = ['妥当', '適切', '正しい', 'どう思う', '判断', '評価', '分析']

# Discord Bot初期化
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==========================================
# 1. データベース管理 (aiosqlite)
# ==========================================
async def init_db():
    async with aiosqlite.connect(BotConfig.DB_NAME) as db:
        # ユーザー管理 (Level/XP)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1
            )
        """)
        # 設定 (AutoRole, Welcome)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                autorole_id INTEGER,
                welcome_channel_id INTEGER
            )
        """)
        # AI使用ログ (1日制限用)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                user_id INTEGER,
                date TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, date)
            )
        """)
        await db.commit()

# ==========================================
# 2. 起動処理
# ==========================================
@bot.event
async def on_ready():
    await init_db()
    logger.info(f"ログイン完了: {bot.user} (GPT Model: {OpenAIConfig.GPT_MODEL})")
    
    # 永続Viewの登録（再起動後もボタンが動くように）
    bot.add_view(ScheduleView())
    bot.add_view(TicketCreateView())
    
    # スラッシュコマンド同期
    try:
        await bot.tree.sync()
        logger.info("スラッシュコマンド同期完了")
    except Exception as e:
        logger.error(f"コマンド同期エラー: {e}")

    # ステータス更新
    update_status.start()

@tasks.loop(minutes=30)
async def update_status():
    activity = discord.Activity(type=discord.ActivityType.listening, name="表現の自由について")
    await bot.change_presence(activity=activity)

# ==========================================
# 3. AI機能 (茜ちゃん & 規制分析)
# ==========================================
class ExpressionAnalyzer:
    """表現規制分析ロジック"""
    def detect(self, text: str) -> bool:
        has_kw = any(k in text for k in BotConfig.REGULATION_KEYWORDS)
        has_qs = any(k in text for k in BotConfig.QUESTION_KEYWORDS) or '?' in text or '？' in text
        return has_kw and has_qs

    def create_prompt(self, text: str) -> str:
        return f"""あなたは「表自派茜」という関西弁の女子高生です。
以下のトピックについて、憲法学の厳格審査基準を用いて分析してください。

【トピック】
{text}

【出力形式】
1. 法律による根拠 (Legal Basis)
2. 正当な目的 (Legitimate Purpose)
3. 必要性・比例性 (Necessity & Proportionality)
上記を5点満点で評価し、最後に関西弁で「妥当」「問題あり」の判定を下してください。
"""

analyzer = ExpressionAnalyzer()

async def call_gpt(system_prompt: str, user_text: str):
    if not client: return "APIキーが設定されてへんわ。"
    
    # モデル判定 (推論モデルかどうか)
    is_reasoning = any(x in OpenAIConfig.GPT_MODEL for x in ["o1", "o3", "gpt-5"])
    
    try:
        params = {
            "model": OpenAIConfig.GPT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        }
        
        if is_reasoning:
            # 推論モデル用 (temperatureなし)
            params["max_completion_tokens"] = 1500
            params["reasoning_effort"] = "medium"
        else:
            # 通常モデル用
            params["max_tokens"] = 1000
            params["temperature"] = 0.8 # 人格維持のため高め

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: client.chat.completions.create(**params))
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"GPT Error: {e}")
        return "あかん、エラーが出てもうたわ💦"

async def check_usage_limit(user_id: int) -> bool:
    """1日の使用回数制限チェック"""
    today = datetime.now(JST).strftime('%Y-%m-%d')
    async with aiosqlite.connect(BotConfig.DB_NAME) as db:
        cursor = await db.execute("SELECT count FROM usage_log WHERE user_id = ? AND date = ?", (user_id, today))
        row = await cursor.fetchone()
        count = row[0] if row else 0
        
        if count >= BotConfig.DAILY_MESSAGE_LIMIT:
            return False
        
        if row:
            await db.execute("UPDATE usage_log SET count = count + 1 WHERE user_id = ? AND date = ?", (user_id, today))
        else:
            await db.execute("INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, 1)", (user_id, today, ))
        await db.commit()
    return True

# ==========================================
# 4. イベントハンドラ (会話・XP)
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot: return

    # --- AIチャット機能 ---
    if isinstance(message.channel, discord.DMChannel) or bot.user in message.mentions:
        # 使用制限チェック
        if not await check_usage_limit(message.author.id):
            await message.reply("今日の会話回数はこれでおしまいや。また明日な！")
            return

        user_text = re.sub(r'<@!?\d+>', '', message.content).strip()
        
        async with message.channel.typing():
            # 規制分析モードか通常会話か
            if analyzer.detect(user_text):
                prompt = analyzer.create_prompt(user_text)
                is_analysis = True
            else:
                prompt = f"あなたは「表自派茜」という元気な関西弁の女子高生です。ユーザー({message.author.display_name})と楽しく会話してください。"
                is_analysis = False
            
            response = await call_gpt(prompt, user_text)
            
            if is_analysis:
                embed = discord.Embed(title="📋 茜の分析結果", description=response[:4000], color=discord.Color.gold())
                await message.reply(embed=embed)
            else:
                await message.reply(response)

    # --- XP (レベル) システム ---
    if message.guild:
        async with aiosqlite.connect(BotConfig.DB_NAME) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
            row = await cursor.fetchone()
            
            xp_add = 10
            if row:
                xp, level = row
                xp += xp_add
                if xp >= level * 100: # 簡易レベルアップ式
                    xp = 0
                    level += 1
                    await message.channel.send(f"🎉 {message.author.mention} が **Level {level}** に上がったで！")
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, message.author.id))
            else:
                await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (message.author.id, xp_add, 1))
            await db.commit()

    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    # AutoRole & Welcome
    async with aiosqlite.connect(BotConfig.DB_NAME) as db:
        # Welcome
        c = await db.execute("SELECT welcome_channel_id FROM settings WHERE guild_id = ?", (member.guild.id,))
        row = await c.fetchone()
        if row and row[0]:
            ch = member.guild.get_channel(row[0])
            if ch:
                embed = discord.Embed(title="Welcome!", description=f"{member.mention} さん、ようこそ！", color=discord.Color.orange())
                embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(embed=embed)
        
        # AutoRole
        c = await db.execute("SELECT autorole_id FROM settings WHERE guild_id = ?", (member.guild.id,))
        row = await c.fetchone()
        if row and row[0]:
            role = member.guild.get_role(row[0])
            if role:
                await member.add_roles(role)

# ==========================================
# 5. スケジュール機能
# ==========================================
class ScheduleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_schedule(self, interaction, status):
        embed = interaction.message.embeds[0]
        user = interaction.user
        new_fields = []
        target_name = f"【{status}】"
        
        for field in embed.fields:
            # 既存リストから自分を消す
            lines = field.value.split('\n')
            lines = [l for l in lines if user.mention not in l and "なし" not in l]
            
            if field.name == target_name:
                lines.append(f"• {user.mention}")
            
            val = '\n'.join(lines) if lines else "なし"
            new_fields.append((field.name, val))
        
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
        new_embed.set_footer(text=embed.footer.text)
        new_embed.timestamp = embed.timestamp
        for n, v in new_fields:
            new_embed.add_field(name=n, value=v, inline=True)
            
        await interaction.response.edit_message(embed=new_embed)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, custom_id="sch_join")
    async def join(self, interaction, button): await self.update_schedule(interaction, "参加")
    
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger, custom_id="sch_leave")
    async def leave(self, interaction, button): await self.update_schedule(interaction, "不参加")
    
    @discord.ui.button(label="保留", style=discord.ButtonStyle.secondary, custom_id="sch_maybe")
    async def maybe(self, interaction, button): await self.update_schedule(interaction, "保留")

@bot.tree.command(name="schedule", description="スケジュール調整パネルを作成")
async def schedule(interaction: discord.Interaction, title: str, date: str, time: str):
    """date: 2025/01/01, time: 21:00"""
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y/%m/%d %H:%M")
        ts = int(dt.timestamp())
        time_dsp = f"<t:{ts}:F> (<t:{ts}:R>)"
    except:
        await interaction.response.send_message("日時は `YYYY/MM/DD` `HH:MM` で頼むわ！", ephemeral=True)
        return

    embed = discord.Embed(title=f"📅 {title}", description=f"日時: {time_dsp}", color=discord.Color.brand_green())
    embed.add_field(name="【参加】", value="なし", inline=True)
    embed.add_field(name="【不参加】", value="なし", inline=True)
    embed.add_field(name="【保留】", value="なし", inline=True)
    embed.set_footer(text=f"作成者: {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, view=ScheduleView())

# ==========================================
# 6. 管理・チケット・便利機能
# ==========================================
# 管理コマンドグループ
class AdminGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="admin", description="管理機能")

    @app_commands.command(name="kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction, member: discord.Member, reason: str = "なし"):
        await member.kick(reason=reason)
        await interaction.response.send_message(f"{member.mention} をKickしたで。(理由: {reason})")

    @app_commands.command(name="clear")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"{amount}件 削除したで。", ephemeral=True)

bot.tree.add_command(AdminGroup())

# チケット機能
class TicketCreateView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="問い合わせ", style=discord.ButtonStyle.primary, emoji="📩", custom_id="tk_create")
    async def create(self, interaction, button):
        ch = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}")
        await ch.set_permissions(interaction.user, read_messages=True)
        await ch.set_permissions(interaction.guild.default_role, read_messages=False)
        await interaction.response.send_message(f"チケット作ったで: {ch.mention}", ephemeral=True)
        await ch.send(f"{interaction.user.mention} ここで内容を書いてな。", view=TicketCloseView())

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.danger)
    async def close(self, interaction, button):
        await interaction.response.send_message("ほな閉じるで〜")
        await asyncio.sleep(3)
        await interaction.channel.delete()

@bot.tree.command(name="setup_ticket", description="[管理者] チケットパネル設置")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction):
    await interaction.channel.send("📩 お問い合わせはこちらから", view=TicketCreateView())
    await interaction.response.send_message("設置完了！", ephemeral=True)

# 投票機能
@bot.tree.command(name="poll", description="投票を作成")
async def poll(interaction, question: str, opt1: str, opt2: str):
    embed = discord.Embed(title=f"📊 {question}", description=f"1️⃣ {opt1}\n2️⃣ {opt2}", color=discord.Color.gold())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("1️⃣")
    await msg.add_reaction("2️⃣")
    await interaction.response.send_message("投票作ったで", ephemeral=True)

# 設定系 (Welcome/AutoRole)
@bot.tree.command(name="set_welcome", description="[管理者] Welcomeチャンネル設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome(interaction, channel: discord.TextChannel):
    async with aiosqlite.connect(BotConfig.DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (guild_id, welcome_channel_id) VALUES (?, ?)", (interaction.guild.id, channel.id))
        await db.commit()
    await interaction.response.send_message(f"Welcome先を {channel.mention} にしたで！")

@bot.tree.command(name="set_autorole", description="[管理者] オートロール設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_autorole(interaction, role: discord.Role):
    async with aiosqlite.connect(BotConfig.DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO settings (guild_id, autorole_id) VALUES (?, ?)", (interaction.guild.id, role.id))
        await db.commit()
    await interaction.response.send_message(f"オートロールを {role.name} にしたで！")

# ==========================================
# メイン実行
# ==========================================
if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("エラー: DISCORD_TOKEN が設定されてへんで！")
