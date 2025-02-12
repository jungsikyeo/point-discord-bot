import os
import sys
import logging
import hashlib
import math
import time
from discord import Member
from discord.commands.context import ApplicationContext
from DiscordLevelingCard import RankCard, Settings
from datetime import datetime, timedelta
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
import level_main as base_bot

bot = base_bot.bot
db = base_bot.db

bot_token = os.getenv("BOT_LEVEL_TOKEN")
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))
guild_ids = list(map(int, os.getenv('GUILD_ID').split(',')))
enabled_channel_list = list(map(int, os.getenv('XP_ENABLED_CHANNEL_LIST').split(',')))
no_xp_roles = list(map(int, os.getenv('NO_XP_ROLE_LIST').split(',')))
level_2_role_id = int(os.getenv('LEVEL_2_ROLE_ID'))
level_5_role_id = int(os.getenv('LEVEL_5_ROLE_ID'))
level_10_role_id = int(os.getenv('LEVEL_10_ROLE_ID'))
level_12_role_id = int(os.getenv('LEVEL_12_ROLE_ID'))
level_15_role_id = int(os.getenv('LEVEL_15_ROLE_ID'))
level_20_role_id = int(os.getenv('LEVEL_20_ROLE_ID'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f"level_{folder_name}.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"This is an info message from level_{folder_name}")


@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.bot:
        return

    # 메시지가 지정된 채널 또는 역할에서 오지 않은 경우 무시
    if message.channel.id not in enabled_channel_list or any(role.id in no_xp_roles for role in message.author.roles):
        return

    user_id = message.author.id
    user_name = message.author.name
    guild_id = message.guild.id
    message_hash = hashlib.sha256(message.content.encode()).hexdigest()
    points = 0

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select sysdate() as current_db_time
                from dual
            """)
            current_time = cursor.fetchone()['current_db_time']

            # 사용자의 마지막 메시지 정보 조회
            cursor.execute("""
                SELECT last_message_time
                FROM user_levels_trala
                WHERE user_id = %s  AND guild_id = %s 
            """, (user_id, guild_id))
            last_message = cursor.fetchone()

            if last_message:
                cursor.execute("""
                    SELECT message_time
                    FROM user_message_logs_trala
                    WHERE user_id = %s  AND guild_id = %s 
                    AND message_time > %s  AND message_time <= %s 
                    AND message_hash = %s
                    ORDER BY message_time DESC
                    LIMIT 1
                """, (user_id, guild_id, current_time - timedelta(seconds=120), current_time, message_hash))
                check_message = cursor.fetchone()

                # 2분 이내 동일 채팅인 경우 패스
                if not check_message:
                    # print((current_time.timestamp() - last_message['last_message_time'].timestamp()))
                    # 45초 이내 채팅인 경우 패스
                    if (current_time.timestamp() - last_message['last_message_time'].timestamp()) > 45:
                        # 메시지 필터링 및 포인트 계산 로직
                        cursor.execute("""
                            SELECT COUNT(DISTINCT message_hash) AS filtered_count
                            FROM user_message_logs_trala
                            WHERE user_id = %s AND guild_id = %s 
                            AND message_time > %s 
                            AND message_time <= %s
                        """, (user_id, guild_id, current_time - timedelta(seconds=120), current_time))
                        filtered_result = cursor.fetchone()
                        filtered_count = filtered_result['filtered_count'] if filtered_result else 0

                        if filtered_count >= 2:
                            points = (math.sqrt(filtered_count) ** (1/3)) * 13
                        else:
                            points = 0

                        # logger.info(f"{user_name} -> {points}")

                        if points > 0:
                            cursor.execute("""
                                select xp
                                from user_levels_trala
                                WHERE user_id = %s AND guild_id = %s
                            """, (user_id, guild_id))
                            user_level = cursor.fetchone()

                            current_xp = int(user_level['xp'])

                            cursor.execute("""
                                UPDATE user_levels_trala
                                SET xp = xp + %s, last_message_time = %s
                                WHERE user_id = %s AND guild_id = %s
                            """, (points, current_time, user_id, guild_id))
                            connection.commit()

                            old_level = base_bot.rank_to_level(current_xp)['level']
                            new_level = base_bot.rank_to_level(current_xp + points)['level']

                            if old_level != new_level:
                                # LEVEL UP => role check
                                logger.info(f"{user_name} ({user_id}) LEVEL{old_level} -> LEVEL{new_level}")
                                await base_bot.set_level_to_roles(guild_id, user_id, new_level)

            else:
                # logger.info(f"{user_name} -> new")
                cursor.execute("""
                    INSERT INTO user_levels_trala (user_id, guild_id, xp, last_message_time)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, guild_id, points, current_time))
                connection.commit()

            cursor.execute("""
                INSERT INTO user_message_logs_trala (user_id, guild_id, xp, message_hash, message_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, guild_id, points, message_hash, current_time))
            connection.commit()
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        connection.rollback()
    finally:
        connection.close()

    await bot.process_commands(message)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)

    base_bot.folder_name = folder_name
    base_bot.level_2_role_id = level_2_role_id
    base_bot.level_5_role_id = level_5_role_id
    base_bot.level_10_role_id = level_10_role_id
    base_bot.level_12_role_id = level_12_role_id
    base_bot.level_15_role_id = level_15_role_id
    base_bot.level_20_role_id = level_20_role_id
    base_bot.no_rank_members = list(map(int, os.getenv('NO_RANK_MEMBERS').split(',')))


rank_search_users = {}


@bot.slash_command(
    name="rank",
    description="Show the top active users",
    guild_ids=guild_ids
)
async def get_rank(ctx: ApplicationContext,
                   user: Option(Member, "User to show rank of (Leave empty for personal rank)", required=False)):
    await base_bot.get_rank(ctx, user)


@bot.slash_command(
    name="rank_leaderboard",
    description="Show the top active users",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def rank_leaderboard(ctx: ApplicationContext):
    await base_bot.rank_leaderboard(ctx)


@bot.slash_command(
    name="give_xp",
    description="Add rank XP to user",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def give_xp(ctx: ApplicationContext, member: Member, points: int):
    await base_bot.give_xp(ctx, member, points)


@bot.slash_command(
    name="remove_xp",
    description="Remove rank XP to user",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def remove_xp(ctx: ApplicationContext, member: Member, xp: int):
    await base_bot.remove_xp(ctx, member, xp)


@bot.slash_command(
    name="reset_leaderboard_stats",
    description="Delete the XP stats and remove roles",
    guild_ids=guild_ids
)
@commands.has_any_role(*team_role_ids)
async def reset_leaderboard_stats(ctx: ApplicationContext):
    await base_bot.reset_leaderboard_stats(ctx)


bot.run(bot_token)
