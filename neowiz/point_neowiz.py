import os
import sys
import logging
from discord.ext import commands
from discord import Role
from typing import Union
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

bot_token = os.getenv("BOT_POINT_TOKEN")
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))
no_xp_roles = list(map(int, os.getenv('NO_XP_ROLE_LIST').split(',')))


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
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def store_setting(ctx):
    await base_bot.store_setting(ctx)


@bot.command(
    name='store-main'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def store_main(ctx):
    await base_bot.store_main(ctx)


@bot.command(
    name='add-item'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def add_item(ctx):
    await base_bot.add_item(ctx)


@bot.command(
    name='give-rewards'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def give_rewards(ctx, user_tag, amount):
    await base_bot.give_rewards(ctx, user_tag, amount)


@bot.command(
    name='remove-rewards'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def remove_rewards(ctx, user_tag, amount):
    await base_bot.remove_rewards(ctx, user_tag, amount)


@bot.command(
    name='give-role-rewards'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def give_role_rewards(ctx, role: Union[Role, int, str], amount):
    await base_bot.give_role_rewards(ctx, role, amount)


@bot.command(
    name='giveaway-raffle'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def giveaway_raffle(ctx):
    await base_bot.giveaway_raffle(ctx)


# @bot.command(
#     name='today'
# )
# async def today(ctx):
#     today_channel_id = os.getenv("TODAY_CHANNEL_ID")
#     today_self_rewards_amount = int(os.getenv("TODAY_SELF_REWARDS_AMOUNT"))
#     if ctx.channel.id == int(today_channel_id):
#         await base_bot.today_self_rewards(ctx, today_self_rewards_amount)


@bot.command(
    name='level-rewards'
)
@commands.has_any_role(*mod_role_ids)
async def level_rewards(ctx):
    await base_bot.level_rewards(ctx)


@bot.command(
    name='level-reset'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def level_reset(ctx):
    await base_bot.level_reset(ctx)


@bot.command(
    name='level-list'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def level_list(ctx):
    await base_bot.level_list(ctx)


@bot.command(
    name='bulk-add-role'
)
@commands.has_any_role(*team_role_ids, *mod_role_ids)
async def bulk_add_role(ctx, role: Union[Role, int, str]):
    await base_bot.bulk_add_role(ctx, role)


@bot.command(name="export-role")
async def export_role_members(ctx, role: str = None):
    await base_bot.export_role_members(ctx, role)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)
    # bot.add_cog(base_bot.RaffleCog(bot, db))

    # guild_id = int(os.getenv("GUILD_ID"))
    # call_channel_id = int(os.getenv("ALPHA_CALL_CHANNEL_ID"))
    # announce_channel_id = int(os.getenv("ALPHA_CALL_ANNOUNCE_CHANNEL_ID"))
    # base_bot.alpha_call_rewards.start(guild_id, call_channel_id, announce_channel_id)
    base_bot.event_role_channel_id = int(os.getenv("EVENT_ROLE_CHANNEL_ID"))  # 이벤트 채널 ID 설정
    base_bot.log_channel_id = int(os.getenv("LOG_CHANNEL_ID"))
    base_bot.no_xp_roles = no_xp_roles


bot.run(bot_token)
