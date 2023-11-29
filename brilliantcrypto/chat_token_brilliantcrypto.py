import os
import sys
import logging
from discord.ext import commands
from dotenv import load_dotenv

current_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_path)
folder_name = os.path.basename(current_dir)
env_path = os.path.join(current_dir, f".env_{folder_name}")


load_dotenv(dotenv_path=env_path)

parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import chat_token_main as base_bot

bot = base_bot.bot
db = base_bot.db

bot_token = os.getenv("BOT_TOKEN")
guild_id = os.getenv("GUILD_ID")
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))
exclude_role_list = list(map(int, os.getenv('C2E_EXCLUDE_ROLE_LIST').split(',')))
enabled_channel_list = list(map(int, os.getenv('C2E_ENABLED_CHANNEL_LIST').split(',')))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f"chat_token_{folder_name}.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"This is an info message from chat_token_{folder_name}")


@bot.command(
    name="chat-token-stats"
)
@commands.has_any_role(*mod_role_ids)
async def chat_token_stats(ctx, log_date="today"):
    await base_bot.chat_token_stats(ctx, log_date)


@bot.command(
    name="setting-chat-token"
)
@commands.has_any_role(*team_role_ids)
async def setting_chat_token(ctx):
    await base_bot.setting_chat_token(ctx)


@bot.event
async def on_ready():
    # 봇이 준비되었을 때 실행할 코드
    base_bot.config_logging(logger)
    logger.info(f"{guild_id}: {bot.user} is now online!")
    await base_bot.on_ready(guild_id, enabled_channel_list)


@bot.event
async def on_message(message):
    # 봇 자신의 메시지는 처리하지 않음
    if message.author.bot:
        return

    # 특정 역할을 가진 사용자의 메시지는 무시
    if any(role.id in exclude_role_list for role in message.author.roles):
        await bot.process_commands(message)
        return

    # 메시지가 허용된 채널 중 하나에서 왔는지 확인
    if message.channel.id not in enabled_channel_list:
        await bot.process_commands(message)
        return

    await base_bot.on_message(message, bot)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    else:
        logger.error(f"An error occurred: {str(error)}")


bot.run(bot_token)
