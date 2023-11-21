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
import point_main as base_bot

bot = base_bot.bot
db = base_bot.db

bot_token = os.getenv("BOT_TOKEN")
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f"point_{folder_name}.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"This is an info message from point_{folder_name}")


@bot.command(
    name='store-setting'
)
@commands.has_any_role(*team_role_ids)
async def store_setting(ctx):
    await base_bot.store_setting(ctx)


@bot.command(
    name='store-main'
)
@commands.has_any_role(*team_role_ids)
async def store_main(ctx):
    await base_bot.store_main(ctx)


@bot.command(
    name='add-item'
)
@commands.has_any_role(*team_role_ids)
async def add_item(ctx):
    await base_bot.add_item(ctx)


@bot.command(
    name='give-rewards'
)
@commands.has_any_role(*mod_role_ids)
async def give_rewards(ctx, user_tag, amount):
    await base_bot.give_rewards(ctx, user_tag, amount)


@bot.command(
    name='remove-rewards'
)
@commands.has_any_role(*mod_role_ids)
async def remove_rewards(ctx, user_tag, amount):
    await base_bot.remove_rewards(ctx, user_tag, amount)


@bot.command(
    name='giveaway-raffle'
)
@commands.has_any_role(*mod_role_ids)
async def giveaway_raffle(ctx):
    await base_bot.giveaway_raffle(ctx)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)
    bot.add_cog(base_bot.RaffleCog(bot, db))


bot.run(bot_token)
