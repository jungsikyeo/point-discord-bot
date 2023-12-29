import discord
import os
import re
import db_pool
import point_main
from discord.ext import commands
from discord.commands.context import ApplicationContext
from discord.interactions import Interaction
from discord.ui import View, button, Modal, InputText
from discord import Embed, ButtonStyle
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


class LotterySettingButton(View):
    def __init__(self, lottery):
        super().__init__()
        self.lottery = lottery

    @button(label="Change Setting", style=discord.ButtonStyle.primary, custom_id="button_change_setting")
    async def button_lottery_information(self, _, interaction):
        await interaction.response.send_modal(modal=LotterySettingModal(db, self.lottery))


class LotterySettingModal(Modal):
    def __init__(self, db, lottery):
        super().__init__(title="Lottery Game Setting")
        self.db = db
        self.raffle_numbers = InputText(label="Raffle Numbers",
                                        placeholder="Numbers between 1 and 6",
                                        value=lottery.get('raffle_numbers', ''),
                                        custom_id="raffle_numbers",
                                        max_length=2, )
        self.ticket_price = InputText(label="Ticket Price",
                                      placeholder="ticket price",
                                      value=lottery.get('ticket_price', ''),
                                      custom_id="ticket_price",
                                      max_length=10, )
        self.max_ticket_count = InputText(label="Max Ticket Count",
                                          placeholder="max ticket count",
                                          value=lottery.get('max_ticket_count', ''),
                                          custom_id="max_ticket_count",
                                          max_length=10, )
        self.add_item(self.raffle_numbers)
        self.add_item(self.ticket_price)
        self.add_item(self.max_ticket_count)

    async def callback(self, interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                    select id, raffle_numbers, ticket_price, max_ticket_count, round_status
                    from lottery_rounds
                    where guild_id = %s
                    and round_status = 'OPEN'
                """,
                (guild_id,)
            )
            lottery = cursor.fetchone()

            raffle_numbers = int(self.raffle_numbers.value)
            ticket_price = int(self.ticket_price.value)
            max_ticket_count = int(self.max_ticket_count.value)

            if raffle_numbers < 1 or raffle_numbers > 6:
                description = "```❌ Invalid input. Please enter numbers between 1 and 6 only.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'StoreSettingModal error: Invalid input. Please enter numbers between 1 and 6 only.')
                return

            if lottery:
                lottery_id = lottery.get("id")
                cursor.execute(
                    """
                        update lottery_rounds 
                        set
                             raffle_numbers = %s,
                             ticket_price = %s,
                             max_ticket_count = %s
                        where id = %s
                    """,
                    (lottery_id, raffle_numbers, max_ticket_count, ticket_price)
                )
            else:
                cursor.execute(
                    """
                        insert into lottery_rounds (guild_id, raffle_numbers, ticket_price, max_ticket_count)
                        values (%s, %s, %s, %s)
                    """,
                    (guild_id, raffle_numbers, ticket_price, max_ticket_count)
                )

            description = f"Lottery Game information has been saved."
            embed = make_embed({
                'title': '✅ Lottery Game save complete',
                'description': description,
                'color': 0xFFFFFF,
            })
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            connection.commit()
        except ValueError:
            # 숫자로 변환할 수 없는 입력이 있는 경우
            description = "```❌ Invalid input. Please enter numbers only.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotterySettingModal db error: Invalid input. Please enter numbers only.')
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotterySettingModal db error: {e}')
        finally:
            cursor.close()
            connection.close()


class LotteryMainView(View):
    def __init__(self, db, guild_id, lottery_id):
        super().__init__(timeout=None)
        self.db = db
        self.guild_id = guild_id
        self.lottery_id = lottery_id

    @button(label="Buy Ticket", style=discord.ButtonStyle.green, custom_id="buy_ticket_button")
    async def button_buy_ticket(self, _, interaction: Interaction):
        user_id = interaction.user.id
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                    with round as (
                        select id, raffle_numbers, ticket_price, max_ticket_count, round_status
                        from lottery_rounds
                        where id = %s
                        and round_status = 'OPEN'
                    )
                    select id,
                           raffle_numbers,
                           ticket_price,
                           max_ticket_count,
                           round_status,
                           (
                               select count(1)
                               from lottery_user_tickets
                               where lottery_id = round.id
                                 and user_id = %s
                           ) buy_ticket_count
                    from round
                """,
                (self.lottery_id, user_id)
            )
            lottery = cursor.fetchone()

            ticket_price = int(lottery.get("ticket_price"))
            max_ticket_count = int(lottery.get("max_ticket_count"))
            buy_ticket_cnt = int(lottery.get("buy_ticket_count"))

            if max_ticket_count > buy_ticket_cnt:
                modal = LotteryPurchaseModal(self.db, self.guild_id, self.lottery_id, ticket_price)
                await interaction.response.send_modal(modal)
            else:
                description = "```❌ Maximum purchase limit has been exceeded.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'button_buy_ticket error: Maximum purchase limit has been exceeded.')
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_buy_ticket error: {e}')
        finally:
            cursor.close()
            connection.close()


class LotteryPurchaseModal(Modal):
    def __init__(self, db, guild_id, lottery_id, ticket_price):
        super().__init__(title="Buy Lottery Ticket")
        self.db = db
        self.guild_id = guild_id
        self.lottery_id = lottery_id
        self.ticket_price = ticket_price
        self.add_item(InputText(label="Numbers", placeholder="6 Numbers between 1 and 45"))

    async def callback(self, interaction: Interaction):
        # 입력된 텍스트를 콤마와 공백으로 분리하여 숫자 리스트 생성
        input_numbers = re.split(r'[,\s]+', self.children[0].value)

        # 입력된 숫자들이 6개인지 확인
        if len(input_numbers) != 6:
            description = "```❌ Please enter exactly 6 numbers.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotteryPurchaseModal error: Please enter exactly 6 numbers.')
            return

        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            # 입력된 숫자들을 정수 리스트로 변환
            numbers = [int(num) for num in input_numbers]

            # 모든 숫자가 1에서 45 사이인지 확인
            if not all(1 <= num <= 45 for num in numbers):
                description = "```❌ Numbers must be between 1 and 45.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'LotteryPurchaseModal error: Numbers must be between 1 and 45.')
                return

            # 중복된 숫자가 없는지 확인
            if len(set(numbers)) != 6:
                description = "```❌ Numbers must not be duplicated.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'LotteryPurchaseModal error: Numbers must not be duplicated.')
                return

            # 사용자에게 선택한 숫자를 보여주고 구매할지 확인
            user_input_numbers = ', '.join(map(str, numbers))
            user_input_numbers_emoji = ""
            for number in numbers:
                if number == 1:
                    user_input_numbers_emoji += f":one: "
                elif number == 2:
                    user_input_numbers_emoji += f":two: "
                elif number == 3:
                    user_input_numbers_emoji += f":three: "
                elif number == 4:
                    user_input_numbers_emoji += f":four: "
                elif number == 5:
                    user_input_numbers_emoji += f":five: "
                elif number == 6:
                    user_input_numbers_emoji += f":six: "
                elif number == 7:
                    user_input_numbers_emoji += f":seven: "
                elif number == 8:
                    user_input_numbers_emoji += f":eight: "
                elif number == 9:
                    user_input_numbers_emoji += f":nine: "
                elif number == 10:
                    user_input_numbers_emoji += f":keycap_ten: "
                else:
                    guild_emojis = interaction.guild.emojis
                    for guild_emoji in guild_emojis:
                        if f"lottery_{number}" == guild_emoji.name:
                            user_input_numbers_emoji += f"{guild_emoji} "
                            break
            confirmation_message = f"You have chosen the numbers:\n{user_input_numbers_emoji}\n\n" \
                                   f"Ticket Price: `{self.ticket_price} points`\n\n" \
                                   f"Do you want to proceed with the purchase?"
            await interaction.response.send_message(content=confirmation_message,
                                                    view=ConfirmPurchaseView(self.db, self.lottery_id, user_input_numbers, self.ticket_price, interaction),
                                                    ephemeral=True)
        except ValueError:
            # 숫자로 변환할 수 없는 입력이 있는 경우
            connection.rollback()
            description = "```❌ Invalid input. Please enter numbers only.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotteryPurchaseModal error: Invalid input. Please enter numbers only.')
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotteryPurchaseModal error: {e}')
        finally:
            cursor.close()
            connection.close()


class ConfirmPurchaseView(View):
    def __init__(self, db, lottery_id, user_input_numbers, ticket_price, org_interaction: Interaction):
        super().__init__()
        self.db = db
        self.lottery_id = lottery_id
        self.user_input_numbers = user_input_numbers
        self.ticket_price = ticket_price
        self.org_interaction = org_interaction

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm_purchase(self, _, interaction: Interaction):
        guild_id = str(interaction.guild.id)
        user_id = interaction.user.id
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            # 포인트 차감 및 로또 번호 저장 로직 구현
            cursor.execute(
                """
                    select points
                    from user_points
                    where guild_id = %s 
                    and user_id = %s
                """,
                (guild_id, user_id,)
            )
            user = cursor.fetchone()

            if user:
                user_points = int(user.get('points'))
            else:
                user_points = 0

            if user_points < int(self.ticket_price):
                description = "```❌ Not enough points.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'confirm_purchase price error: Not enough points.')
                return
            else:
                cursor.execute(
                    """
                        insert into lottery_user_tickets (guild_id, lottery_id, user_id, numbers)
                        values (%s, %s, %s, %s)
                    """,
                    (guild_id, self.lottery_id, user_id, self.user_input_numbers)
                )

                connection.commit()

                params = {
                    'user_id': user_id,
                    'point': int(self.ticket_price) * -1,
                    'action_user_id': user_id,
                    'action_type': 'buy-lottery-ticket',
                }
                result = await point_main.save_rewards(interaction, params)

                if result.get('success') > 0:
                    description = f"Purchase completed. Good luck!\n\n" \
                                  f"{interaction.user.mention} points: `{result.get('before_user_points')}` -> `{result.get('after_user_points')}`"
                    embed = make_embed({
                        'title': '✅ Ticket purchase completed',
                        'description': description,
                        'color': 0xFFFFFF,
                    })
                    await self.org_interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LotteryPurchaseModal error: {e}')
        finally:
            cursor.close()
            connection.close()

    @button(label="Cancel", style=ButtonStyle.red)
    async def cancel_purchase(self, _, interaction: Interaction):
        await interaction.response.defer()
        await self.org_interaction.edit_original_response(content="❌ Purchase cancelled.",
                                                          view=None)


bot = commands.Bot(command_prefix=command_flag, intents=discord.Intents.all())
db = db_pool.Database(mysql_ip, mysql_port, mysql_id, mysql_passwd, mysql_db)


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


async def lottery_setting(ctx: ApplicationContext):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
                select id, raffle_numbers, ticket_price, max_ticket_count, round_status
                from lottery_rounds
                where guild_id = %s
                and round_status = 'OPEN'
            """,
            (guild_id,)
        )
        lottery = cursor.fetchone()

        raffle_numbers = lottery.get('raffle_numbers') if lottery else None
        ticket_price = lottery.get('ticket_price') if lottery else None
        max_ticket_count = lottery.get('max_ticket_count') if lottery else None
        round_status = lottery.get('round_status') if lottery else 'CLOSE'

        description = f"⚙️ Press the `Change Setting` button to setting lottery game.\n\n"
        embed = make_embed({
            'title': 'Current Lottery Game Setting Information',
            'description': description,
            'color': 0xFFFFFF,
        })

        embed.add_field(name="Raffle Numbers", value=f"```{raffle_numbers if raffle_numbers else 'Not yet.'}```", inline=False)
        embed.add_field(name="Ticker Price", value=f"```{ticket_price if ticket_price else 'Not yet.'}```", inline=False)
        embed.add_field(name="Max Ticket Count", value=f"```{max_ticket_count if max_ticket_count else 'Not yet.'}```", inline=False)
        embed.add_field(name="Round Status", value=f"```{round_status}```", inline=False)

        lottery = {
            'raffle_numbers': raffle_numbers,
            'ticket_price': ticket_price,
            'max_ticket_count': max_ticket_count,
            'round_status': round_status
        }

        view = LotterySettingButton(lottery)
        await ctx.respond(embed=embed, view=view, ephemeral=True)
    except Exception as e:
        logger.error(f'lottery_setting db error: {e}')
    finally:
        cursor.close()
        connection.close()


async def start_lottery(ctx: ApplicationContext):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
                select id, raffle_numbers, ticket_price, max_ticket_count, round_status
                from lottery_rounds
                where guild_id = %s
                and round_status = 'OPEN'
            """,
            (guild_id,)
        )
        lottery = cursor.fetchone()

        if lottery:
            lottery_id = lottery.get("id")
            description = "Let's start the lottery game.\n\n" \
                          "Enter 6 numbers separated by spaces or commas (e.g. 1, 23, 45, 19, 36, 5)\n\n" \
                          "Press the button below to buy a lottery ticket!"
            embed = make_embed({
                'title': ':tickets: Start Lottery Game',
                'description': description,
                'color': 0xFFFFFF,
            })
            view = LotteryMainView(db, guild_id, lottery_id)
            await ctx.respond(embed=embed, view=view, ephemeral=False)
        else:
            description = "```❌ No rounds have been opened in lottery game yet.```"
            await ctx.respond(description, ephemeral=True)
            logger.error(f'start_lottery error: No rounds have been opened in lottery game yet.')
            return
    except Exception as e:
        logger.error(f'start_lottery error: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()
