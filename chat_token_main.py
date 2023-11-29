import discord
import os
import datetime
import random
import asyncio
import pytz
import db_pool
from dotenv import load_dotenv
from discord.ext import commands
from discord import Embed
from discord.ui import View, button, Modal, InputText
from discord.ext.pages import Paginator
from discord.interactions import Interaction
from datetime import datetime, timedelta

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

tokens_data = {}
winner_users = {}
used_verify_lm = []
weekly_top = []

guild_id = ""
channel_list = []
token_type = "SF"
searchfi_amount = 100
min_win = 1
max_win = 5
win_limit = 4

lock_status = True

c2e_type = os.getenv("C2E_TYPE")


class TokenSettingsModal(Modal):
    def __init__(self, data):
        super().__init__(title=f"{token_type} Token Settings")
        self.add_item(InputText(label="Daily Token Limit",
                                placeholder="Enter the daily token limit",
                                value=f"{data.get('daily_token_limit')}"))
        self.add_item(InputText(label="Minimum Tokens per Win",
                                placeholder="Enter the minimum tokens per win",
                                value=f"{data.get('min_win')}"))
        self.add_item(InputText(label="Maximum Tokens per Win",
                                placeholder="Enter the maximum tokens per win",
                                value=f"{data.get('max_win')}"))
        self.add_item(InputText(label="Win Limit per User",
                                placeholder="Enter the win limit per user",
                                value=f"{data.get('win_limit')}"))

    async def callback(self, interaction: Interaction):
        global guild_id

        # 데이터베이스 업데이트 로직
        daily_limit = self.children[0].value
        min_tokens = self.children[1].value
        max_tokens = self.children[2].value
        user_limit = self.children[3].value

        connection = db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                UPDATE c2e_token_tracking 
                SET 
                    daily_token_limit = %s,
                    min_win = %s,
                    max_win = %s,
                    win_limit = %s
                WHERE guild_id = %s
            """, (daily_limit, min_tokens, max_tokens, user_limit, guild_id))
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f'TokenSettingsModal db error: {e}')
        finally:
            cursor.close()
            connection.close()

        await interaction.response.send_message(f"{token_type} Token settings updated successfully!", ephemeral=True)


# 버튼 클래스 정의
class TokenSettingsButton(View):
    def __init__(self, db):
        super().__init__()
        self.db = db

    @button(label="setting", style=discord.ButtonStyle.primary, custom_id="setting_sftoken_button")
    async def button_add_setting(self, _, interaction: Interaction):
        global guild_id
        data = {}
        connection = db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT 
                    daily_token_limit,
                    min_win,
                    max_win,
                    win_limit
                FROM c2e_token_tracking
                WHERE guild_id = %s
            """, guild_id)
            data = cursor.fetchone()
        except Exception as e:
            connection.rollback()
            logger.error(f'button_add_setting db error: {e}')
        finally:
            cursor.close()
            connection.close()
        await interaction.response.send_modal(modal=TokenSettingsModal(data))


class StatsButtons(View):
    def __init__(self, db, ctx, today_string):
        super().__init__()
        self.db = db
        self.ctx = ctx
        self.today_string = today_string

    @discord.ui.button(label="Token By Cycles",
                       style=discord.ButtonStyle.primary,
                       custom_id="token_cycles_button")
    async def button_token_cycles(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        global guild_id, token_type

        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(f"""
                select
                    id,
                    (select max(timestamp) from user_point_logs where guild_id = {guild_id} and id < a.id) before_times,
                    timestamp current_times,
                    (timestampdiff(MINUTE , (select max(timestamp) from user_point_logs where guild_id = {guild_id} and id < a.id),timestamp)) minus_time,
                    point_amount as tokens
                from user_point_logs a
                where guild_id = '{guild_id}'
                and action_type = 'chat'
                and timestamp like concat('{self.today_string}', '%')
            """)
            token_log = cursor.fetchall()
            num_pages = (len(token_log) + 14) // 15
            pages = []
            for page in range(num_pages):
                embed = Embed(title=f"{token_type} Token Stats By Cycles - Page {page + 1}",
                              description="- **Before Times**: The Before times the token was sent\n"
                                          "- **Current Times**: The Current times the token was sent\n"
                                          "- **Cycle**: Cycles in which tokens were sent\n"
                                          f"- **Tokens**: {token_type} Tokens sent to the user",
                              color=0x9da1ef)
                header = "```\n{:<21}{:<20}{:<8}{:>6}\n".format("Before Times", "Current Times", "Cycle", "Tokens")
                line = "-" * (20 + 20 + 9 + 6) + "\n"  # 각 열의 너비 합만큼 하이픈 추가
                description = header + line
                for i in range(15):
                    index = page * 15 + i
                    if index >= len(token_log):
                        break
                    log = token_log[index]
                    before_times = log['before_times'].strftime("%Y-%m-%d %H:%M:%S") if log['before_times'] else "N/A"
                    current_times = log['current_times'].strftime("%Y-%m-%d %H:%M:%S")
                    minus_time = str(log['minus_time']) + " min"
                    tokens = str(int(log['tokens'])) + f" {token_type}"
                    description += "{:<21}{:<20}{:>8}{:>6}\n".format(before_times, current_times, minus_time, tokens)
                description += "```"

                embed.add_field(name="",
                                value=description)
                pages.append(embed)
            paginator = Paginator(pages)
            await paginator.send(self.ctx, mention_author=True)
        except Exception as e:
            connection.rollback()
            logger.error(f'Error in button_token_cycles: {e}')
        finally:
            cursor.close()
            connection.close()

    @discord.ui.button(label="Token By Channels",
                       style=discord.ButtonStyle.green,
                       custom_id="token_channels_button")
    async def button_token_channels(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        global guild_id, token_type

        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            dual_table = ""
            index = 0
            for channel in channel_list:
                if index > 0:
                    dual_table += "union all "
                dual_table += "select distinct '1' as id, " \
                            f"'{channel}' channel_id, " \
                            f"'{bot.get_channel(int(channel))}' channel_name " \
                            "from dual "
                index += 1

            cursor.execute(f"""
                with times as (
                    select distinct '1' as id,
                                    FROM_UNIXTIME(UNIX_TIMESTAMP(timestamp), '%Y-%m-%d %H') times
                    from user_point_logs
                    where guild_id = '{guild_id}' 
                    and timestamp like concat('{self.today_string}', '%')
                ),
                times_channels as (
                    select times.times,
                          channels.channel_id,
                          channels.channel_name
                   from times
                    inner join ({dual_table}) as channels on channels.id = times.id
                )
                select tc.times,
                       tc.channel_id,
                       tc.channel_name,
                       ifnull(stats.cnt, 0) as cnt,
                       ifnull(stats.sum_tokens, 0) as sum_tokens
                from times_channels as tc
                left outer join (
                    select FROM_UNIXTIME(UNIX_TIMESTAMP(timestamp), '%Y-%m-%d %H') as times,
                           channel_id,
                           channel_name,
                           count(1) cnt,
                           sum(point_amount) sum_tokens
                    from user_point_logs as main
                    where guild_id = '{guild_id}' 
                    and action_type = 'chat'
                    and timestamp like concat('{self.today_string}', '%')
                    group by FROM_UNIXTIME(UNIX_TIMESTAMP(timestamp), '%Y-%m-%d %H'),
                             channel_id,
                             channel_name
                ) as stats on stats.times = tc.times
                            and stats.channel_id = tc.channel_id
                order by tc.times,
                         tc.channel_name
            """)
            token_log = cursor.fetchall()
            num_pages = (len(token_log) + 15) // 16
            pages = []
            for page in range(num_pages):
                embed = Embed(title=f"{token_type} Token Stats By Channels - Page {page + 1}",
                              description="- **Times**: KST Time the token was sent (in hours)\n"
                                          "- **Channel Name**: The channel where the token was won\n"
                                          "- **COUNT**: Number of tokens won\n"
                                          "- **SUM**: Total of winning tokens",
                              color=0x9da1ef)
                header = "```\n{:<15}{:<15}{:<5}{:>7}\n".format("Times", "Channel Name", "COUNT", "SUM")
                line = "-" * (15 + 15 + 5 + 7) + "\n"  # 각 열의 너비 합만큼 하이픈 추가
                description = header + line
                for i in range(16):
                    index = page * 16 + i
                    if index >= len(token_log):
                        break
                    if i > 0 and i % 4 == 0:
                        description += line
                    log = token_log[index]
                    times = log['times']
                    channel_name = f"{bot.get_channel(int(log['channel_id']))}"
                    count = str(log['cnt'])
                    sum_tokens = str(int(log['sum_tokens'])) + f" {token_type}"
                    description += "{:<15}{:<15}{:>5}{:>7}\n".format(times, channel_name, count, sum_tokens)
                description += "```"

                embed.add_field(name="",
                                value=description)
                pages.append(embed)
            paginator = Paginator(pages)
            await paginator.send(self.ctx, mention_author=True)
        except Exception as e:
            connection.rollback()
            logger.error(f'Error in button_token_channels: {e}')
        finally:
            cursor.close()
            connection.close()

    @discord.ui.button(label="Token By Users",
                       style=discord.ButtonStyle.red,
                       custom_id="token_users_button")
    async def button_token_users(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        global guild_id, token_type

        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(f"""
                select channel_id,
                       channel_name,
                       user_id,
                       count(1) cnt,
                       sum(point_amount) sum_tokens
                from user_point_logs
                where guild_id = '{guild_id}' 
                and action_type = 'chat'
                and timestamp like concat('{self.today_string}', '%')
                group by channel_id, channel_name, user_id
                order by sum_tokens desc
            """)
            token_log = cursor.fetchall()
            num_pages = (len(token_log) + 14) // 15
            pages = []
            for page in range(num_pages):
                embed = Embed(title=f"{token_type} Token Stats By Users - Page {page + 1}",
                              description="- **Channel Name**: The channel where the token was won\n"
                                          "- **User Name**: User Name where the token was won\n"
                                          "- **COUNT**: Number of tokens won\n"
                                          "- **SUM**: Total of winning tokens",
                              color=0x9da1ef)
                header = "```\n{:<15}{:<25}{:<5}{:>7}\n".format("Channel Name", "User Name", "COUNT", "SUM")
                line = "-" * (15 + 25 + 5 + 7) + "\n"  # 각 열의 너비 합만큼 하이픈 추가
                description = header + line
                for i in range(15):
                    index = page * 15 + i
                    if index >= len(token_log):
                        break
                    log = token_log[index]
                    channel_name = f"{bot.get_channel(int(log['channel_id']))}"
                    user = interaction.guild.get_member(int(log['user_id']))
                    count = str(log['cnt'])
                    sum_tokens = str(int(log['sum_tokens'])) + f" {token_type}"
                    description += "{:<15}{:<25}{:>5}{:>7}\n".format(channel_name, user.display_name, count, sum_tokens)
                description += "```"

                embed.add_field(name="",
                                value=description)
                pages.append(embed)
            paginator = Paginator(pages)
            await paginator.send(self.ctx, mention_author=True)
        except Exception as e:
            connection.rollback()
            logger.error(f'Error in button_token_users: {e}')
        finally:
            cursor.close()
            connection.close()


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
    embed.set_footer(text="Powered by SearchFi DEV")
    return embed


async def chat_token_stats(ctx, log_date="today"):
    if log_date == "today":
        target_date = datetime.now()
        today = target_date
        today_string = today.strftime("%Y-%m-%d")
    else:
        today_string = log_date

    embed = make_embed({
        "title": f"{token_type} Token Stats",
        "description": f"Query statistics for date `{today_string}`."
        "Please select the type of statistics you want to look up with the button below.",
        "color": 0xFFFFFF})
    view = StatsButtons(db, ctx, today_string)
    await ctx.reply(embed=embed, view=view, mention_author=True)


async def setting_chat_token(ctx):
    embed = make_embed({
        "title": f"{token_type} Token Settings",
        "description": f"Please setting {token_type} Token using the button below.",
        "color": 0xFFFFFF})
    view = TokenSettingsButton(db)
    await ctx.reply(embed=embed, view=view, mention_author=True)


# 한국 시간대 기준 정오(낮 12시) 시간 구하기
def get_noon_kst():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    return noon.timestamp() if now >= noon else (noon - timedelta(days=1)).timestamp()


# 기준 시간으로부터 최대 지속 시간 내에서 무작위 시간 생성
def random_time(base, max_duration):
    return base + random.randint(0, max_duration)


async def on_ready(current_guild_id, enabled_channel_list):
    global guild_id, channel_list
    guild_id = current_guild_id
    channel_list = enabled_channel_list

    # 데이터베이스 연결
    connection = db.get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT type, reset_at, still_available, daily_token_limit, min_win, max_win, win_limit
            FROM c2e_token_tracking WHERE guild_id = %s
        """, (guild_id,))
        data = cursor.fetchone()

        global token_type, searchfi_amount, min_win, max_win, win_limit, lock_status

        # 토큰 초기화 및 스케줄링
        if not data:
            next_reset = get_noon_kst()
            cursor.execute("""
                INSERT INTO c2e_token_tracking (guild_id, type, reset_at) 
                VALUES (%s, %s, %s) 
            """, (guild_id, token_type, next_reset))

            cursor.execute("""
                SELECT reset_at, still_available, daily_token_limit, min_win, max_win, win_limit
                FROM c2e_token_tracking WHERE guild_id = %s
            """, (guild_id,))
            data = cursor.fetchone()

            searchfi_amount = data['still_available']
            min_win = data['min_win']
            max_win = data['max_win']
            win_limit = data['win_limit']

        # 커밋
        connection.commit()

        logger.info(
            f"on_ready: {datetime.fromtimestamp(data['reset_at'])}, {data['still_available']}")

        asyncio.create_task(schedule_reset(False))

        lock_status = False

    except Exception as e:
        logger.error(f'Error in on_ready: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


async def schedule_reset(run_type=True):
    global guild_id, token_type

    # 토큰 정보 가져오기
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        global searchfi_amount, min_win, max_win, win_limit
        cursor.execute("""
                SELECT reset_at, still_available, daily_token_limit, min_win, max_win, win_limit
                FROM c2e_token_tracking WHERE guild_id = %s
            """, (guild_id,))
        data = cursor.fetchone()

        token_amount = data['daily_token_limit']
        min_win = data['min_win']
        max_win = data['max_win']
        win_limit = data['win_limit']

        if run_type:
            next_reset = int(data['reset_at']) + 43200  # 다음 리셋 시간 계산

            # 데이터베이스에서 토큰 리셋 시간 업데이트
            cursor.execute("""
                UPDATE c2e_token_tracking SET reset_at = %s, still_available = %s 
                WHERE type = %s
            """, (next_reset, token_amount, token_type))

            connection.commit()
        else:
            next_reset = int(data['reset_at'])

        # 토큰 데이터 리셋
        global winner_users, tokens_data
        tokens_data[token_type] = None
        winner_users = {}

        await schedule_give()

        # 다음 리셋까지 대기
        await asyncio.sleep(next_reset - datetime.now().timestamp())

        # 다음 리셋 스케줄링
        logger.info(f"resetting tokens at, {datetime.fromtimestamp(next_reset)}, {token_type}")
    except Exception as e:
        connection.rollback()
        logger.error(f'schedule_reset db error: {e}')
    finally:
        cursor.close()
        connection.close()
        asyncio.create_task(schedule_reset())


async def schedule_give():
    global guild_id, token_type

    # 토큰 정보 가져오기
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        # 남은 토큰 수량 확인
        cursor.execute("""
            SELECT reset_at, still_available FROM c2e_token_tracking WHERE guild_id = %s
        """, (guild_id,))
        result = cursor.fetchone()
        reset_at = datetime.fromtimestamp(result['reset_at'])
        available = result['still_available']

        # 평균 토큰 지급량 계산
        average_tokens_per_distribution = (min_win + max_win) / 2  # min_win, max_win 개의 평균

        # 남은 시간 계산
        now = datetime.now()
        remaining_seconds = (reset_at - now).total_seconds()

        # 새로운 토큰 지급 주기 계산
        if available > 0:
            new_rate = remaining_seconds / (available / average_tokens_per_distribution)
            random_offset = random.randint(-90, 90)  # -1분 30초 ~ +1분 30초
            next_give_time = now.timestamp() + new_rate + random_offset
        else:
            next_give_time = reset_at.timestamp()  # 토큰이 없으면 다음 리셋 시간으로 설정

        # 토큰 지급 시간 업데이트
        tokens_data[token_type] = next_give_time

        logger.info("Next give time: %s", datetime.fromtimestamp(next_give_time))
    except Exception as e:
        connection.rollback()
        logger.error(f'schedule_give db error: {e}')
    finally:
        cursor.close()
        connection.close()


async def on_message(message, bot):
    # tokensData와 winnerUsers를 확인하여 토큰 지급 여부 결정
    global winner_users, tokens_data, lock_status, token_type
    current_timestamp = datetime.now().timestamp()
    if not lock_status and tokens_data.get(token_type) and current_timestamp > tokens_data[token_type]:
        if not winner_users.get(message.author.id) or winner_users[message.author.id] < win_limit:
            lock_status = True
            # searchfi 토큰 지급
            await give_points(message)
            await schedule_give()
            lock_status = False

    # 명령어 처리를 위해 기본 on_message 핸들러 호출
    await bot.process_commands(message)


async def give_points(message):
    global guild_id, token_type

    # 데이터베이스 연결 및 토큰 정보 업데이트
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        # 해당 토큰 유형의 남은 토큰 양 확인
        cursor.execute("""
            SELECT still_available FROM c2e_token_tracking WHERE guild_id = %s
        """, (guild_id,))
        available = cursor.fetchone()['still_available']

        # 랜덤 토큰 양 계산
        rand = random.randint(min_win, max_win)
        token_amount = available if available - rand < min_win else rand

        # 남은 토큰 양 업데이트
        cursor.execute("""
            UPDATE c2e_token_tracking SET still_available = still_available - %s 
            WHERE guild_id = %s
        """, (token_amount, guild_id))

        cursor.execute("""
            SELECT user_id, points
            FROM user_points
            WHERE guild_id = %s
            AND user_id = %s
        """, (guild_id, message.author.id))
        user = cursor.fetchone()

        if user:
            # 사용자 토큰 증`가
            cursor.execute("""
                UPDATE user_points
                SET points = points + %s
                WHERE guild_id = %s
                AND user_id = %s
            """, (token_amount, guild_id, message.author.id))
        else:
            # 사용자 토큰 증가
            cursor.execute("""
                INSERT INTO user_points (guild_id, user_id, points) VALUES (%s, %s, %s)
            """, (guild_id, message.author.id, token_amount))

        # 사용자 토큰 부여 로그
        cursor.execute("""
            INSERT INTO user_point_logs (
                guild_id, user_id, point_amount, action_user_id, channel_id, channel_name, action_type
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (guild_id, message.author.id, token_amount,
              'bot', message.channel.id, message.channel.name, 'chat'))
        logger.info(f"{message.channel.name} -> {message.author.name} : {token_amount}")

        if not winner_users.get(message.author.id):
            winner_users[message.author.id] = 1
        else:
            winner_users[message.author.id] += 1

        # 커밋
        connection.commit()

        # 메시지 임베드 생성
        embed = make_embed({
            "title": "Congratulations 🎉 🎉",
            "description": f"You just won **{token_amount}** {token_type} tokens!",
            "color": 0x9da1ef,
            "image_url": "https://cdn.discordapp.com/attachments/955428076651679846/1091499808960811008/IMG_0809.gif"
        })

        # 메시지 전송
        await message.reply(embed=embed)
    except Exception as e:
        connection.rollback()
        logger.error(f'Error in give_points: {e}')
    finally:
        cursor.close()
        connection.close()
