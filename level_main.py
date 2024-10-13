import discord
import os
import db_pool
import math
import time
from discord import Member
from discord.commands import Option
from discord.commands.context import ApplicationContext
from discord.ext import commands
from discord import Embed
from datetime import datetime
from DiscordLevelingCard import RankCard, Settings
from discord.ext.pages import Paginator
from dotenv import load_dotenv

load_dotenv()

command_flag = os.getenv("SEARCHFI_BOT_FLAG")
mysql_ip = os.getenv("MYSQL_IP")
mysql_port = os.getenv("MYSQL_PORT")
mysql_id = os.getenv("MYSQL_ID")
mysql_passwd = os.getenv("MYSQL_PASSWD")
mysql_db = os.getenv("MYSQL_DB")


global logger


def config_logging(module_logger):
    global logger
    logger = module_logger


bot = commands.Bot(command_prefix=command_flag, intents=discord.Intents.all())
db = db_pool.Database(mysql_ip, mysql_port, mysql_id, mysql_passwd, mysql_db)

folder_name = None
level_2_role = None
level_5_role = None
level_10_role = None
level_2_role_id = None
level_5_role_id = None
level_10_role_id = None
level_12_role_id = None
level_15_role_id = None
level_20_role_id = None
no_rank_members = None

def make_embed(embed_info):
    embed = Embed(
        title=embed_info.get('title', ''),
        description=embed_info.get('description', ''),
        color=embed_info.get('color', 0xFFFFFF),
    )
    if embed_info.get('image_url', None):
        embed.set_image(
            url=embed_info.get('image_url')
        )
    # embed.set_footer(text="Powered by SearchFi DEV")
    return embed


bulk = {
    "flag": False,
    "func": ""
}


def change_bulk(flag, func):
    global bulk
    bulk = {
        "flag": flag,
        "func": func
    }


def rank_to_level(org_xp: int):
    if not org_xp or org_xp < 0:
        return {
            "xp": 0,
            "level": 0,
            "total_xp": int(math.pow(2, 4))
        }

    curr_level = math.floor(math.pow(org_xp, 1/4))
    offset = 0 if curr_level == 1 else math.pow(curr_level, 4)
    xp = org_xp - offset
    xp_required = math.pow(curr_level + 1, 4) - offset

    return {
        "xp": int(xp),
        "level": curr_level - 1,
        "total_xp": int(xp_required)
    }


async def set_level_to_roles(local_server, user_id: int, level: int):
    global level_2_role, level_5_role, level_10_role, level_2_role_id, level_5_role_id, level_10_role_id, level_12_role_id, level_15_role_id, level_20_role_id
    level_2_role = bot.get_guild(local_server).get_role(level_2_role_id)
    level_5_role = bot.get_guild(local_server).get_role(level_5_role_id)
    level_10_role = bot.get_guild(local_server).get_role(level_10_role_id)
    level_12_role = bot.get_guild(local_server).get_role(level_12_role_id)
    level_15_role = bot.get_guild(local_server).get_role(level_15_role_id)
    level_20_role = bot.get_guild(local_server).get_role(level_20_role_id)

    searchfi = bot.get_guild(local_server)
    user = searchfi.get_member(int(user_id))

    if level >= 20:
        await user.add_roles(level_2_role)
        await user.add_roles(level_5_role)
        await user.add_roles(level_10_role)
        await user.add_roles(level_12_role)
        await user.add_roles(level_15_role)
        await user.add_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: x, Add: 2, 5, 10, 12, 15, 20")
    elif 20 > level >= 15:
        await user.add_roles(level_2_role)
        await user.add_roles(level_5_role)
        await user.add_roles(level_10_role)
        await user.add_roles(level_12_role)
        await user.add_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 20 Add: 2, 5, 10, 12, 15")
    elif 15 > level >= 12:
        await user.add_roles(level_2_role)
        await user.add_roles(level_5_role)
        await user.add_roles(level_10_role)
        await user.add_roles(level_12_role)
        await user.remove_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 15, 20 Add: 2, 5, 10, 12")
    elif 12 > level >= 10:
        await user.add_roles(level_2_role)
        await user.add_roles(level_5_role)
        await user.add_roles(level_10_role)
        await user.remove_roles(level_12_role)
        await user.remove_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 12, 15, 20 Add: 2, 5, 10")
    elif 10 > level >= 5:
        await user.add_roles(level_2_role)
        await user.add_roles(level_5_role)
        await user.remove_roles(level_10_role)
        await user.remove_roles(level_12_role)
        await user.remove_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 10, 12, 15, 20 Add: 2, 5")
    elif 5 > level >= 2:
        await user.add_roles(level_2_role)
        await user.remove_roles(level_5_role)
        await user.remove_roles(level_10_role)
        await user.remove_roles(level_10_role)
        await user.remove_roles(level_12_role)
        await user.remove_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 5, 10, 12, 15, 20 Add: 2")
    else:
        await user.remove_roles(level_2_role)
        await user.remove_roles(level_5_role)
        await user.remove_roles(level_10_role)
        await user.remove_roles(level_12_role)
        await user.remove_roles(level_15_role)
        await user.remove_roles(level_20_role)
        logger.info(f"{user_id} -> Delete: 2, 5, 10, 12, 15, 20 Add: x")


rank_search_users = {}


async def get_rank(ctx: ApplicationContext,
                   user: Option(Member, "User to show rank of (Leave empty for personal rank)", required=False)):
    if not user:
        user = ctx.user

    user_name = user.name
    user_id = user.id
    guild_id = user.guild.id

    current_time = time.time()
    if rank_search_users and rank_search_users.get(user_id, None) and ctx.user.id not in no_rank_members:
        prev_time = rank_search_users.get(user_id, current_time)
        time_spent = current_time - prev_time
        doing_time = datetime.fromtimestamp(prev_time + 60*60*8)    # 8시간 딜레이 세팅
        doting_timestamp = int(doing_time.timestamp())
        if time_spent < 60*60*8:
            embed = make_embed({
                "title": "Error",
                "description": "Rank command inquiry is possible every 8 hours.\n"
                               f"Your next command query time is <t:{doting_timestamp}>",
                "color": 0xff0000,
            })
            await ctx.respond(embed=embed, ephemeral=True)
            return

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            if not user:
                user = ctx.user

            cursor.execute(f"""
                select user_id, xp, user_rank
                from (
                    select user_id, xp, rank() over(order by xp desc, last_message_time) as user_rank
                    from user_levels_{folder_name}
                    where guild_id = %s
                    order by xp desc
                ) as user_ranks
                where user_id = %s
            """, (guild_id, user_id))
            data = cursor.fetchone()

            if data:
                org_xp = data['xp']
                rank = data['user_rank']
            else:
                org_xp = 0
                rank = 0

            data = rank_to_level(org_xp)

            await ctx.defer()

            card_settings = Settings(
                background="level_card.png",
                text_color="white",
                bar_color="#ffffff"
            )

            user_level = data['level']
            user_xp = data['xp']
            user_total_xp = data['total_xp']

            rank_card = RankCard(
                settings=card_settings,
                avatar=user.display_avatar.url,
                level=user_level,
                current_exp=user_xp,
                max_exp=user_total_xp,
                username=f"{user_name}",
                rank=rank
            )
            image = await rank_card.card2()
            await ctx.respond(file=discord.File(image, filename=f"rank.png"), ephemeral=False)

            rank_search_users[user_id] = current_time
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        connection.rollback()
        embed = make_embed({
            "title": "Error",
            "description": f"An error occurred: {str(e)}",
            "color": 0xff0000,
        })
        await ctx.respond(embed=embed, ephemeral=True)
    finally:
        connection.close()


async def rank_leaderboard(ctx: ApplicationContext):
    guild_id = ctx.guild.id

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            global bulk
            if bulk.get("flag"):
                embed = make_embed({
                    "title": "Warning",
                    "description": f"Bulk operation is in progress, please try again later.",
                    "color": 0xff0000,
                })
                await ctx.respond(embed=embed, ephemeral=True)
                logger.warning(f"Bulk operation is in progress, func: {bulk.get('func')}")
                return

            change_bulk(True, "rank_leaderboard")

            no_rank_members_str = ','.join([f"{member_id}" for member_id in no_rank_members])

            cursor.execute(f"""
                select user_id, xp, rank() over(order by xp desc, last_message_time) as user_rank
                from user_levels_{folder_name}
                where guild_id = %s
                and user_id not in({no_rank_members_str})
                order by xp desc
            """, guild_id)
            db_users = cursor.fetchall()

            num_pages = (len(db_users) + 14) // 15
            pages = []
            for page in range(num_pages):
                description = ""
                for i in range(15):
                    index = page * 15 + i
                    if index >= len(db_users):
                        break
                    ranker = db_users[index]
                    user_rank = ranker['user_rank']
                    user_id = int(ranker['user_id'])
                    user = ctx.guild.get_member(user_id)
                    if user:
                        user_mention = user.mention
                    else:
                        user_mention = f"<@{user_id}>"
                    org_xp = ranker['xp']
                    rank_info = rank_to_level(org_xp)
                    user_level = rank_info['level']
                    user_xp = rank_info['xp']

                    description += f"`{user_rank}.` {user_mention} • Level **{user_level}** - **{user_xp}** XP\n"
                embed = make_embed({
                    "title": f"Leaderboard Page {page + 1}",
                    "description": description,
                    "color": 0x37e37b,
                })
                pages.append(embed)
            paginator = Paginator(pages, disable_on_timeout=False, timeout=None)
            await paginator.respond(ctx.interaction, ephemeral=False)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        connection.rollback()
        embed = make_embed({
            "title": "Error",
            "description": f"An error occurred: {str(e)}",
            "color": 0xff0000,
        })
        await ctx.respond(embed=embed, ephemeral=True)
    finally:
        change_bulk(False, "")
        connection.close()


async def give_xp(ctx: ApplicationContext, member: Member, points: int):
    guild_id = ctx.guild.id
    user_id = member.id

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select sysdate() as current_db_time
                from dual
            """)
            current_time = cursor.fetchone()['current_db_time']

            cursor.execute(f"""
                select xp
                from user_levels_{folder_name}
                WHERE user_id = %s AND guild_id = %s
            """, (user_id, guild_id))
            user_level = cursor.fetchone()

            if user_level:
                current_xp = int(user_level['xp'])

                add_points = points
                if current_xp + points < 0:
                    add_points = current_xp * (-1)

                cursor.execute(f"""
                    UPDATE user_levels_{folder_name}
                    SET xp = xp + %s, last_message_time = %s
                    WHERE user_id = %s AND guild_id = %s
                """, (add_points, current_time, user_id, guild_id))
            else:
                current_xp = 0

                cursor.execute(f"""
                    insert into user_levels_{folder_name} (guild_id, user_id, xp, last_message_time) 
                    values (%s, %s, %s, %s)
                """, (guild_id, user_id, points, current_time))

            connection.commit()

            old_level = rank_to_level(current_xp)['level']
            new_level = rank_to_level(current_xp + points)['level']

            if old_level != new_level:
                await set_level_to_roles(guild_id, user_id, new_level)

            embed = make_embed({
                "title": "XP successfully added",
                "description": f"✅ Successfully added {points} XP to {member.mention}",
                "color": 0x37e37b,
            })
            await ctx.respond(embed=embed, ephemeral=False)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        connection.rollback()
        embed = make_embed({
            "title": "Error",
            "description": f"An error occurred: {str(e)}",
            "color": 0xff0000,
        })
        await ctx.respond(embed=embed, ephemeral=True)
    finally:
        connection.close()


async def remove_xp(ctx: ApplicationContext, member: Member, xp: int):
    await give_xp(ctx, member, xp*(-1))


async def reset_leaderboard_stats(ctx: ApplicationContext):
    guild_id = ctx.guild.id

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            await ctx.defer()

            global bulk
            if bulk.get("flag"):
                embed = make_embed({
                    "title": "Warning",
                    "description": f"Bulk operation is in progress, please try again later.",
                    "color": 0xff0000,
                })
                await ctx.respond(embed=embed, ephemeral=True)
                logger.warning(f"Bulk operation is in progress, func: {bulk.get('func')}")
                return

            change_bulk(True, "reset_leaderboard_stats")

            role_lvs = [level_2_role_id, level_5_role_id, level_10_role_id, level_12_role_id, level_15_role_id, level_20_role_id]

            cursor.execute(f"""
                delete from user_levels_{folder_name} where guild_id = %s
            """, guild_id)

            cursor.execute(f"""
                delete from user_message_logs_{folder_name} where guild_id = %s
            """, guild_id)

            connection.commit()

            for member in ctx.guild.members:
                for role_lv in role_lvs:
                    if member.get_role(role_lv):
                        guild_role_lv = ctx.guild.get_role(role_lv)
                        await member.remove_roles(guild_role_lv)

            embed = make_embed({
                "title": "Leaderboard Reset Completed!",
                "description": f"✅ Leaderboard have been reset successfully",
                "color": 0x37e37b,
            })
            await ctx.respond(embed=embed, ephemeral=False)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        connection.rollback()
        embed = make_embed({
            "title": "Error",
            "description": f"An error occurred: {str(e)}",
            "color": 0xff0000,
        })
        await ctx.respond(embed=embed, ephemeral=True)
    finally:
        connection.close()
        change_bulk(False, "")