import discord
from discord import app_commands
from discord.ext import commands, tasks
import openai
from openai import OpenAI
import os
import asyncio
import aiosqlite # 非同期DB処理（Botの動作停止を防ぐため必須）
import logging
from datetime import datetime, timedelta
import pytz
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

# =========================
# 0. 環境変数・ログ設定
# =========================
load_dotenv()

# Railwayのログに見やすく出力
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class OpenAIConfig:
    # ★ご指定の GPT-5.1 を設定
    GPT_MODEL = "gpt-5.1"

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None
    logger.warning("OpenAI API Keyが見つかりません")

JST = pytz.timezone('Asia/Tokyo')

# =========================
# 1. Bot設定
# =========================
class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    
    # Railway対応: Volume (/data) があればそこを使う
    if os.path.exists("/data"):
        DB_NAME = '/data/akane_2025_fixed.db'
    else:
        DB_NAME = 'akane_2025_fixed.db'

    REGULATION_ANALYSIS_MAX_TOKENS = 1200
    NORMAL_CHAT_MAX_TOKENS = 600
    
    GPT_MODEL = OpenAIConfig.GPT_MODEL

    REGULATION_KEYWORDS = [
        '表現規制', '規制', '検閲', '制限', '禁止', '表現の自由',
        '言論統制', 'センサーシップ', '表現統制', '言論規制',
        '弾圧', '抑圧', 'コンプライアンス', '自主規制'
    ]
    QUESTION_KEYWORDS = [
        '妥当', '適切', '正しい', 'どう思う', 'どう考える',
        '意見', '判断', '評価', 'どうなん', 'どない思う',
        'どうやと思う', 'どうや', '評価して', '分析して'
    ]

# =========================
# 2. データベース管理 (Async対応)
# =========================
class DatabaseManager:
    def __init__(self, db_name: str):
        self.db_name = db_name

    async def init_database(self):
        async with aiosqlite.connect(self.db_name) as db:
            # 会話ログ・分析用テーブル
            await db.execute('''CREATE TABLE IF NOT EXISTS usage_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, username TEXT, date TEXT, count INTEGER DEFAULT 0, last_message_at TEXT, UNIQUE(user_id, date))''')
            await db.execute('''CREATE TABLE IF NOT EXISTS conversation_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, message TEXT, response TEXT, is_regulation_analysis BOOLEAN, timestamp TEXT, response_time_ms INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS regulation_analysis (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, regulation_target TEXT, question TEXT, legal_basis_score INTEGER, legitimate_purpose_score INTEGER, proportionality_score INTEGER, overall_judgment TEXT, detailed_analysis TEXT, timestamp TEXT)''')
            
            # 汎用Bot機能用テーブル (設定・XP)
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, autorole_id INTEGER, welcome_channel_id INTEGER)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1)''')
            await db.commit()
        logger.info(f"DB initialized: {self.db_name}")

    async def get_user_usage_today(self, user_id: str, username: str = None) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            today = datetime.now(JST).strftime('%Y-%m-%d')
            cursor = await db.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
            result = await cursor.fetchone()
            if username and result:
                await db.execute('UPDATE usage_log SET username = ? WHERE user_id = ? AND date = ?', (username, user_id, today))
                await db.commit()
            return result[0] if result else 0

    async def increment_user_usage(self, user_id: str, username: str = None) -> int:
        async with aiosqlite.connect(self.db_name) as db:
            today = datetime.now(JST).strftime('%Y-%m-%d')
            now = datetime.now(JST)
            try:
                await db.execute('INSERT INTO usage_log (user_id, username, date, count, last_message_at) VALUES (?, ?, ?, 1, ?)', (user_id, username, today, now.isoformat()))
                new_count = 1
            except aiosqlite.IntegrityError:
                await db.execute('UPDATE usage_log SET count = count + 1, last_message_at = ?, username = COALESCE(?, username) WHERE user_id = ? AND date = ?', (now.isoformat(), username, user_id, today))
                cursor = await db.execute('SELECT count FROM usage_log WHERE user_id = ? AND date = ?', (user_id, today))
                row = await cursor.fetchone()
                new_count = row[0]
            await db.commit()
            return new_count

    async def save_conversation(self, user_id: str, message: str, response: str, is_regulation: bool, response_time_ms: int):
        async with aiosqlite.connect(self.db_name) as db:
            now = datetime.now(JST)
            await db.execute('INSERT INTO conversation_history (user_id, message, response, is_regulation_analysis, response_time_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?)', (user_id, message, response, is_regulation, response_time_ms, now.isoformat()))
            await db.commit()

    async def save_regulation_analysis(self, user_id: str, target: str, question: str, scores: Dict[str, int], judgment: str, analysis: str):
        async with aiosqlite.connect(self.db_name) as db:
            now = datetime.now(JST)
            await db.execute('INSERT INTO regulation_analysis (user_id, regulation_target, question, legal_basis_score, legitimate_purpose_score, proportionality_score, overall_judgment, detailed_analysis, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (user_id, target, question, scores.get('legal', 0), scores.get('purpose', 0), scores.get('proportion', 0), judgment, analysis, now.isoformat()))
            await db.commit()

# =========================
# 3. 表現規制分析ロジック
# =========================
class ExpressionRegulationAnalyzer:
    def __init__(self):
        self.config = BotConfig()

    def detect_regulation_question(self, message: str) -> bool:
        has_regulation = any(k in message for k in self.config.REGULATION_KEYWORDS)
        has_question = any(k in message for k in self.config.QUESTION_KEYWORDS)
        question_patterns = [r'.*？$', r'.*\?$', r'^.*ですか.*', r'^.*やろか.*', r'^.*かな.*']
        return has_regulation and (has_question or any(re.search(p, message) for p in question_patterns))

    def extract_regulation_target(self, message: str) -> str:
        patterns = [r'([^。！？\n]+?)への?(?:表現)?規制', r'([^。！？\n]+?)を?規制', r'([^。！？\n]+?)について.*規制']
        for pattern in patterns:
            m = re.search(pattern, message)
            if m:
                target = m.group(1).strip()
                if len(target) > 1: return target
        return "対象の表現"

    def create_analysis_prompt(self, question: str, target: str) -> str:
        return f"""あなたは表現の自由の専門家である関西弁の女子高生「表自派茜」です。
以下の表現規制について、憲法学の厳格審査基準に従って詳細分析してください。

【分析対象】
規制対象: {target}
質問内容: {question}

【審査フレームワーク】
1. 法律による根拠 (Legal Basis)
2. 正当な目的 (Legitimate Purpose)
3. 必要性・比例性 (Necessity & Proportionality)

【回答条件】
- 一人称は必ず「茜」
- 自然な関西弁
- 各項目ごとに点数(1-5)と理由
- 最終判断（妥当 / 要改善 / 問題あり）
"""

# =========================
# 4. メイン Bot クラス
# =========================
class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=['!', '！'], intents=intents, help_command=None)
        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DB_NAME)
        self.analyzer = ExpressionRegulationAnalyzer()
        self.start_time = datetime.now(JST)
        self.stats = {'total_messages': 0, 'regulation_analyses': 0, 'unique_users': set(), 'errors': 0}

    # ★モデル判定ロジック
    def is_reasoning_model(self) -> bool:
        m = self.config.GPT_MODEL.lower()
        # "gpt-5" または "o1" が含まれていたら推論モデルとみなす
        return "gpt-5" in m or "o1" in m or "reasoning" in m

    async def setup_hook(self):
        await self.db.init_database()
        self.cleanup_old_data.start()
        self.update_stats.start()
        self.add_view(ScheduleView())
        self.add_view(TicketCreateView())

    @tasks.loop(hours=24)
    async def cleanup_old_data(self):
        try:
            async with aiosqlite.connect(self.config.DB_NAME) as db:
                cutoff = (datetime.now(JST) - timedelta(days=30)).isoformat()
                await db.execute('DELETE FROM conversation_history WHERE timestamp < ?', (cutoff,))
                await db.commit()
        except Exception as e:
            logger.error(f"Cleanup Error: {e}")

    @tasks.loop(minutes=30)
    async def update_stats(self):
        if not self.is_ready(): return
        try:
            async with aiosqlite.connect(self.config.DB_NAME) as db:
                today = datetime.now(JST).strftime('%Y-%m-%d')
                cursor = await db.execute('SELECT COUNT(DISTINCT user_id) FROM usage_log WHERE date = ?', (today,))
                row = await cursor.fetchone()
                active = row[0] if row else 0
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"表現の自由 ({active}人)"))
        except Exception as e:
            logger.error(f"Stats Error: {e}")

    async def on_ready(self):
        logger.info(f'茜ちゃん起動！ {self.user}')
        print(f"Model: {self.config.GPT_MODEL}")
        try:
            await self.tree.sync()
            logger.info("Commands Synced")
        except Exception as e:
            logger.error(f"Sync Error: {e}")

    async def on_message(self, message):
        if message.author.bot: return
        # AIチャット
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            await self.handle_chat_message(message)
        # 汎用機能: XP
        if message.guild:
            await self.handle_xp(message)
        await self.process_commands(message)

    async def handle_xp(self, message):
        async with aiosqlite.connect(self.config.DB_NAME) as db:
            cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
            row = await cursor.fetchone()
            if row:
                xp, level = row
                xp += 10
                if xp >= level * 100:
                    xp = 0
                    level += 1
                    await message.channel.send(f"🎉 {message.author.mention} Level Up! -> {level}")
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, message.author.id))
            else:
                await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (message.author.id, 10, 1))
            await db.commit()

    async def handle_chat_message(self, message):
        start_time = datetime.now()
        user_id = str(message.author.id)
        username = message.author.display_name
        self.stats['total_messages'] += 1
        self.stats['unique_users'].add(user_id)

        usage = await self.db.get_user_usage_today(user_id, username)
        if usage >= self.config.DAILY_MESSAGE_LIMIT:
            await message.reply("今日の会話回数は終わりや〜。また明日な！")
            return
        await self.db.increment_user_usage(user_id, username)

        try:
            async with message.channel.typing():
                content = re.sub(r'<@!?\d+>', '', message.content).strip()
                is_reg = self.analyzer.detect_regulation_question(content)

                if is_reg:
                    response = await self.handle_regulation_analysis(content, user_id, username)
                    self.stats['regulation_analyses'] += 1
                else:
                    response = await self.handle_normal_chat(content, user_id, username)

                await self.send_response(message, response, is_reg)
                
                ms = int((datetime.now() - start_time).total_seconds() * 1000)
                await self.db.save_conversation(user_id, content, response, is_reg, ms)

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Chat Error: {e}")
            await message.reply("ごめん、エラーが出てもうたわ💦")

    # ---------- GPT 呼び出し処理 ----------

    async def handle_regulation_analysis(self, message: str, user_id: str, username: str) -> str:
        target = self.analyzer.extract_regulation_target(message)
        prompt = self.analyzer.create_analysis_prompt(message, target)
        
        # 簡易スコア
        scores = {'legal': 3, 'purpose': 3, 'proportion': 3}
        judgment = "要検討"
        
        response = await self.call_gpt_with_retry(
            system_prompt=prompt,
            user_message=message,
            max_tokens=self.config.REGULATION_ANALYSIS_MAX_TOKENS,
            temperature=0.6,
            reasoning_effort="medium"
        )
        
        await self.db.save_regulation_analysis(user_id, target, message, scores, judgment, response)
        return response

    async def handle_normal_chat(self, message: str, user_id: str, username: str) -> str:
        prompt = f"あなたは「表自派茜」という関西弁の女子高生です。ユーザー名: {username}。ユーザーに共感し、明るく振る舞ってください。"
        return await self.call_gpt_with_retry(
            system_prompt=prompt,
            user_message=message,
            max_tokens=self.config.NORMAL_CHAT_MAX_TOKENS,
            temperature=0.8,
            reasoning_effort="medium"
        )

    # ★最重要修正: ここでエラーを完全に回避します
    async def call_gpt_with_retry(
        self, system_prompt: str, user_message: str, max_tokens: int = 500,
        temperature: float = 0.8, reasoning_effort: str = "medium", max_retries: int = 3
    ) -> str:
        
        # モデル名を確認
        is_reasoning = self.is_reasoning_model() # gpt-5 or o1

        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
                params = {
                    "model": self.config.GPT_MODEL,
                    "messages": messages,
                }

                if is_reasoning:
                    # ★ GPT-5.1 の場合: temperature を絶対に含めない
                    # max_tokens ではなく max_completion_tokens を使う場合もありますが
                    # エラーの直接原因は temperature なので、まずはこれを除去
                    params["max_completion_tokens"] = max_tokens
                    params["reasoning_effort"] = reasoning_effort
                    
                    # ここに temperature を書かないことが修正の全てです
                else:
                    # 従来モデル (gpt-4oなど)
                    params["max_tokens"] = max_tokens
                    params["temperature"] = temperature
                    params["frequency_penalty"] = 0.1
                    params["presence_penalty"] = 0.1

                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, lambda: client.chat.completions.create(**params))
                return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"GPT Retry {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to call OpenAI: {e}")
                    return "あかん、APIエラーや... 設定を見直してな。"
                await asyncio.sleep(2 ** attempt)

    async def send_response(self, message, response: str, is_regulation: bool = False):
        if is_regulation:
            embed = discord.Embed(title="📋 茜の分析結果", color=0xffd700, timestamp=datetime.now(JST))
            if len(response) > 4000: response = response[:4000] + "..."
            embed.description = response
            await message.reply(embed=embed)
        else:
            if len(response) > 2000:
                await message.channel.send(response[:2000])
                await message.channel.send(response[2000:])
            else:
                await message.reply(response)

# =========================
# 5. 汎用機能 (View & Command)
# =========================
class ScheduleView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def update(self, i, status):
        embed = i.message.embeds[0]
        user = i.user
        new_fields = []
        target = f"【{status}】"
        for field in embed.fields:
            lines = [l for l in field.value.split('\n') if user.mention not in l and "なし" not in l]
            if field.name == target: lines.append(f"• {user.mention}")
            val = '\n'.join(lines) if lines else "なし"
            new_fields.append((field.name, val))
        new_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
        new_embed.set_footer(text=embed.footer.text)
        new_embed.timestamp = embed.timestamp
        for n, v in new_fields: new_embed.add_field(name=n, value=v)
        await i.response.edit_message(embed=new_embed)
    @discord.ui.button(label="参加", style=discord.ButtonStyle.success, custom_id="sch_join")
    async def join(self, i, b): await self.update(i, "参加")
    @discord.ui.button(label="不参加", style=discord.ButtonStyle.danger, custom_id="sch_lv")
    async def leave(self, i, b): await self.update(i, "不参加")
    @discord.ui.button(label="保留", style=discord.ButtonStyle.secondary, custom_id="sch_my")
    async def maybe(self, i, b): await self.update(i, "保留")

class TicketCreateView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="問い合わせ", style=discord.ButtonStyle.primary, emoji="📩", custom_id="tk_cr")
    async def create(self, i, b):
        ch = await i.guild.create_text_channel(f"ticket-{i.user.name}")
        await i.response.send_message(f"作成したで: {ch.mention}", ephemeral=True)
        await ch.send(f"{i.user.mention} 内容をどうぞ", view=TicketCloseView())

class TicketCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="解決・閉じる", style=discord.ButtonStyle.danger)
    async def close(self, i, b):
        await i.response.send_message("ほな閉じるで〜")
        await asyncio.sleep(3)
        await i.channel.delete()

# =========================
# 6. コマンド登録
# =========================
bot = AkaneBot()

@bot.tree.command(name="schedule", description="スケジュール作成")
async def schedule(interaction: discord.Interaction, title: str, date: str, time: str):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y/%m/%d %H:%M")
        ts = int(dt.timestamp())
        embed = discord.Embed(title=f"📅 {title}", description=f"日時: <t:{ts}:F>", color=discord.Color.green())
        for s in ["参加", "不参加", "保留"]: embed.add_field(name=f"【{s}】", value="なし")
        embed.set_footer(text=f"作成者: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, view=ScheduleView())
    except:
        await interaction.response.send_message("日時は `YYYY/MM/DD` `HH:MM` で頼むわ！", ephemeral=True)

@bot.tree.command(name="setup_ticket", description="[管理者] チケット設置")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket(interaction):
    await interaction.channel.send("📩 サポート窓口", view=TicketCreateView())
    await interaction.response.send_message("設置完了", ephemeral=True)

@bot.tree.command(name="poll", description="投票作成")
async def poll(interaction, question: str, opt1: str, opt2: str):
    embed = discord.Embed(title=f"📊 {question}", description=f"1️⃣ {opt1}\n2️⃣ {opt2}", color=discord.Color.gold())
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("1️⃣")
    await msg.add_reaction("2️⃣")
    await interaction.response.send_message("投票作成完了", ephemeral=True)

@bot.command(name='stats')
async def show_stats(ctx):
    await ctx.send(f"総メッセージ: {bot.stats['total_messages']}, エラー: {bot.stats['errors']}")

@bot.command(name='usage')
async def check_usage(ctx):
    usage = await bot.db.get_user_usage_today(str(ctx.author.id), ctx.author.display_name)
    await ctx.send(f"今日の使用: {usage}回")

@bot.event
async def on_member_join(member):
    async with aiosqlite.connect(bot.config.DB_NAME) as db:
        c = await db.execute("SELECT welcome_channel_id FROM settings WHERE guild_id=?", (member.guild.id,))
        row = await c.fetchone()
        if row and row[0]: 
            ch = member.guild.get_channel(row[0])
            if ch: await ch.send(f"Welcome {member.mention}!")
        c = await db.execute("SELECT autorole_id FROM settings WHERE guild_id=?", (member.guild.id,))
        row = await c.fetchone()
        if row and row[0]:
            role = member.guild.get_role(row[0])
            if role: await member.add_roles(role)

if __name__ == '__main__':
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: DISCORD_TOKEN is missing")
