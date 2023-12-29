import os
import sys
import logging
from discord.ext import commands
from discord.commands import Option
from dotenv import load_dotenv

current_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_path)
folder_name = os.path.basename(current_dir)
env_path = os.path.join(current_dir, f".env_{folder_name}")

load_dotenv(dotenv_path=env_path)

parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import lottery_main as base_bot

bot = base_bot.bot
db = base_bot.db

bot_token = os.getenv("BOT_GAME_TOKEN")
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))
guild_ids = list(map(int, os.getenv('GUILD_ID').split(',')))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f"lottery_{folder_name}.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"This is an info message from lottery_{folder_name}")


@bot.slash_command(
    name='lottery-setting',
    description="Setting lottery game.",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def lottery_setting(ctx):
    await base_bot.lottery_setting(ctx)


@bot.slash_command(
    name='start-lottery',
    description="Start lottery game.",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def start_lottery(ctx):
    await base_bot.start_lottery(ctx)


@bot.slash_command(
    name='end-lottery',
    description="End lottery game and winner raffle.",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def end_lottery(ctx,
                      number1: Option(int, "lottery number 1", min_value=1, max_value=45, required=True),
                      number2: Option(int, "lottery number 2", min_value=1, max_value=45, required=True),
                      number3: Option(int, "lottery number 3", min_value=1, max_value=45, required=True),
                      number4: Option(int, "lottery number 4", min_value=1, max_value=45, required=True),
                      number5: Option(int, "lottery number 5", min_value=1, max_value=45, required=True),
                      number6: Option(int, "lottery number 6", min_value=1, max_value=45, required=True)):
    numbers = [number1, number2, number3, number4, number5, number6]
    await base_bot.end_lottery(ctx, numbers)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)


bot.run(bot_token)
