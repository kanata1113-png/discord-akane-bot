import discord
from discord.ext import commands, tasks
import openai
import httpx
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import pytz
import re
from dotenv import load_dotenv
import logging
import json
from typing import Optional, Dict, List, Tuple

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('akane_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# OpenAI設定
class OpenAIConfig:
    GPT_MODEL = "gpt-5.1"            # ← 新モデル名に更新
    # 他に必要なら、ツール使用／キャッシュ利用の設定もここに追加

client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# タイムゾーン設定（日本時間）
JST = pytz.timezone('Asia/Tokyo')

class BotConfig:
    DAILY_MESSAGE_LIMIT = 100
    MAX_RESPONSE_LENGTH = 2000
    DATABASE_NAME = 'akane_data.db'
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

# （データベース管理クラス等は変更なし／省略可能）

class AkaneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=['!', '！'], intents=intents)

        self.config = BotConfig()
        self.db = DatabaseManager(self.config.DATABASE_NAME)
        self.analyzer = ExpressionRegulationAnalyzer()
        self.start_time = datetime.now(JST)

        self.stats = {
            'total_messages': 0,
            'regulation_analyses': 0,
            'unique_users': set(),
            'errors': 0
        }

    async def setup_hook(self):
        self.cleanup_old_data.start()
        self.update_stats.start()

    async def on_ready(self):
        logger.info(f'茜ちゃんが起動したで〜！ {self.user}')
        logger.info(f'参加サーバー数: {len(self.guilds)}')
        logger.info(f'GPTモデル使用モード: {self.config.GPT_MODEL}')

        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="表現の自由について♪"
        )
        await self.change_presence(activity=activity)

        print("=" * 50)
        print("🌸 表自派茜ボット起動完了！")
        print(f"📊 起動時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🤖 Discord.py: {discord.__version__}")
        print(f"🧠 OpenAI model: {self.config.GPT_MODEL}")
        print("=" * 50)

    async def handle_normal_chat(self, message: str, user_id: str, username: str) -> str:
        system_prompt = self.create_character_prompt(username)
        try:
            return await self.call_gpt_with_retry(
                system_prompt=system_prompt,
                user_message=message,
                max_tokens=self.config.NORMAL_CHAT_MAX_TOKENS,
                reasoning_effort="none",            # 新パラメータ追加
                temperature=0.8
            )
        except Exception as e:
            logger.error(f"通常チャットエラー: {e}")
            return "ちょっと調子悪いみたいや〜😅 もう一回試してくれる？"

    async def call_gpt_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 500,
        reasoning_effort: str = "none",
        max_retries: int = 3
    ) -> str:
        """GPT-5.1 対応版：max_completion_tokens を用い、reasoning_effort パラメータを追加"""
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=self.config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_completion_tokens = max_tokens,        # ← 旧 max_tokens から変更
                    reasoning_effort = reasoning_effort,       # ← 新しく追加
                    # temperature 等のパラメータはモデルがサポートしていない可能性あり
                )
                return response.choices[0].message.content

            except Exception as e:
                logger.warning(f"GPT呼び出し失敗 (試行 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        # 万一ループを抜けたら
        raise RuntimeError("GPT 呼び出しが全試行とも失敗")

# メイン実行部分
if __name__ == '__main__':
    required_env = ['DISCORD_TOKEN', 'OPENAI_API_KEY']
    missing_env = [env for env in required_env if not os.getenv(env)]
    if missing_env:
        logger.error(f"必要な環境変数が設定されていません: {missing_env}")
        exit(1)

    bot = AkaneBot()
    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except discord.LoginFailure:
        logger.error("無効なDiscordトークンです。DISCORD_TOKENを確認してください。")
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
