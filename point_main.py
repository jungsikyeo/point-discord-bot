import time

import discord
import os
import requests
import db_pool
import db_query as query
import raffle
import datetime
import asyncio
import pandas as pd
from discord.ext import tasks, commands
from discord.interactions import Interaction
from discord.ui import View, button, Select, Modal, InputText
from discord import Embed, ButtonStyle, InputTextStyle, Role
from typing import Union
from dotenv import load_dotenv

load_dotenv()

command_flag = os.getenv("SEARCHFI_BOT_FLAG")
mysql_ip = os.getenv("MYSQL_IP")
mysql_port = os.getenv("MYSQL_PORT")
mysql_id = os.getenv("MYSQL_ID")
mysql_passwd = os.getenv("MYSQL_PASSWD")
mysql_db = os.getenv("MYSQL_DB")

global logger
level_reset_status = False


def config_logging(module_logger):
    global logger
    logger = module_logger

    raffle.config_logging(module_logger)


class WelcomeView(View):
    def __init__(self, db):
        super().__init__(timeout=None)
        self.db = db

    @button(label="View Store Item", style=ButtonStyle.danger)
    async def button_items(self, _, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_guild_products(),
                (guild_id,)
            )
            all_products = cursor.fetchall()
            if not all_products:
                description = "```ℹ️ There are no items available.```"
                await interaction.response.send_message(description, ephemeral=True)
                return

            await interaction.response.send_message(
                view=ProductSelectView(self.db, all_products, interaction),
                ephemeral=True
            )
        except Exception as e:
            description = "```❌ There was a problem while trying to retrieve the item.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_items error: {e}')
        finally:
            cursor.close()
            connection.close()

    @button(label="Check Tickets", style=ButtonStyle.primary)
    async def button_my_tickets(self, _, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_guild_user_tickets(),
                (guild_id, user_id,)
            )
            all_user_tickets = cursor.fetchall()
            if not all_user_tickets:
                description = "```ℹ️ There is no ticket you applied for.```"
                await interaction.response.send_message(description, ephemeral=True)
                return

            description = ""
            for user_ticket in all_user_tickets:
                description += f"""`[{user_ticket.get('item_type')}]{user_ticket.get('name')}`     x{user_ticket.get('tickets')}\n"""
            embed = make_embed({
                'title': f"My Tickets",
                'description': description,
                'color': 0xFFFFFF,
            })
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
        except Exception as e:
            description = "```❌ There was a problem loading the ticket you applied for.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_my_tickets error: {e}')
        finally:
            cursor.close()
            connection.close()

    @button(label="Check Balance", style=ButtonStyle.green)
    async def button_check_balance(self, _, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)

        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_guild_user_points(),
                (guild_id, user_id,)
            )
            user = cursor.fetchone()
            if not user:
                user_points = 0
            else:
                user_points = format(int(user.get('points', 0)), ',')
            description = f"You have a total of `{user_points}` points"
            embed = make_embed({
                'title': '💰 Balance 💰',
                'description': description,
                'color': 0xFFFFFF,
            })
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
        except Exception as e:
            description = "```❌ There was a problem loading data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_my_points error: {e}')
        finally:
            cursor.close()
            connection.close()


class ProductSelectView(View):
    def __init__(self, db, all_products, org_interaction: Interaction):
        super().__init__()
        self.db = db
        self.all_products = all_products
        self.org_interaction = org_interaction
        self.options = [discord.SelectOption(
            label=f"""[{product.get('item_type')}] {product.get('name')}""",
            value=product.get('name'),
            description=f"""Type: Price: {product.get('price')}""",
        ) for product in all_products]
        self.add_item(ProductSelect(self.db, self.options, self.all_products, self.org_interaction))

    async def on_timeout(self):
        if self.org_interaction:
            await self.org_interaction.delete_original_response()


class ProductSelect(Select):
    def __init__(self, db, options, all_products, org_interaction: Interaction):
        super().__init__(placeholder='Please choose a item', min_values=1, max_values=1, options=options)
        self.db = db
        self.all_products = all_products
        self.org_interaction = org_interaction

    async def callback(self, interaction: Interaction):
        selected_product = None

        for product in self.all_products:
            if product.get('name') == self.values[0]:
                selected_product = product
                break

        buy_button_view = BuyButton(self.db, selected_product, interaction)

        description = "Please press the `Buy` button below to apply."
        embed = make_embed({
            'title': selected_product.get('name'),
            'description': description,
            'color': 0xFFFFFF,
            'image_url': selected_product.get('image'),
        })
        embed.add_field(name="Price", value=f"```{selected_product.get('price')} points```", inline=True)

        await interaction.response.defer(ephemeral=True)

        await self.org_interaction.edit_original_response(
            embed=embed,
            view=buy_button_view
        )


class BuyButton(View):
    def __init__(self, db, product, org_interaction: Interaction):
        super().__init__()
        self.db = db
        self.product = product
        self.org_interaction = org_interaction

    @button(label="Buy", style=discord.ButtonStyle.primary, custom_id="buy_button")
    async def button_buy(self, _, interaction: Interaction):
        # allow_status = False
        # roles = interaction.user.roles
        # for role in roles:
        #     if "LV.2" == role.name:
        #         allow_status = True
        # if not allow_status:
        #     description = "```❌ You can only purchase it if you have an LV.2 role.```"
        #     await interaction.response.send_message(description, ephemeral=True)
        #     logger.error(f'button_buy error: You can only purchase it if you have an LV.2 role.')
        #     return

        if self.product.get('item_type') == "FCFS":
            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel.id)
            channel_name = bot.get_channel(interaction.channel.id)
            user_id = str(interaction.user.id)
            connection = self.db.get_connection()
            cursor = connection.cursor()

            try:
                buy_quantity = 1

                cursor.execute(
                    query.select_guild_product(),
                    (guild_id, self.product.get('id'),)
                )
                product = cursor.fetchone()

                if product:
                    quantity = int(product.get('quantity'))
                    buy_count = int(product.get('buy_count'))
                    price = int(product.get('price'))

                    if quantity == buy_count:
                        description = "```❌ The purchase has been completed, so there is no quantity left.```"
                        await interaction.response.send_message(description, ephemeral=True)
                        logger.error(f'button_buy error: The purchase has been completed, so there is no quantity left.')
                        return

                    cursor.execute(
                        query.select_guild_user_tickets(),
                        (guild_id, user_id,)
                    )
                    user_tickets = cursor.fetchall()

                    for ticket in user_tickets:
                        if self.product.get('id') == ticket.get('id'):
                            description = "```❌ You have already purchased the prize.```"
                            await interaction.response.send_message(description, ephemeral=True)
                            logger.error(f'button_buy error: You have already purchased the prize.')
                            return
                else:
                    description = "```❌ There was a problem applying for the item.```"
                    await interaction.response.send_message(description, ephemeral=True)
                    logger.error(f'button_buy price error: There was a problem applying for the item.')
                    return

                cursor.execute(
                    query.select_guild_user_points(),
                    (guild_id, user_id,)
                )
                user = cursor.fetchone()

                if user:
                    user_points = int(user.get('points'))
                else:
                    user_points = 0

                if user_points < (price * buy_quantity):
                    description = "```❌ Not enough points.```"
                    await interaction.response.send_message(description, ephemeral=True)
                    logger.error(f'BuyQuantityModal price error: Not enough points.')
                    return
                else:
                    loop = buy_quantity
                    while loop > 0:
                        before_user_point = user_points
                        user_points -= price

                        cursor.execute(
                            query.insert_guild_user_ticket(),
                            (user_id, product.get('id'), guild_id,)
                        )
                        cursor.execute(
                            query.update_guild_user_point(),
                            (user_points, guild_id, user_id,)
                        )
                        cursor.execute(
                            query.insert_guild_user_point_logs(),
                            (guild_id, user_id, price * (-1),
                             before_user_point, user_points, 'item-buy', user_id,
                             channel_id, channel_name)
                        )
                        loop -= 1

                    description = f"You applied for the `[{self.product.get('item_type')}]{self.product.get('name')}` x{buy_quantity} item."
                    embed = make_embed({
                        'title': '✅ Item buy completed',
                        'description': description,
                        'color': 0xFFFFFF,
                    })
                    await interaction.response.send_message(
                        embed=embed,
                        ephemeral=True
                    )
                connection.commit()
            except Exception as e:
                connection.rollback()
                description = "```❌ There was a problem processing the data.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'button_buy db error: {e}')
            finally:
                cursor.close()
                connection.close()
        else:
            await interaction.response.send_modal(modal=BuyQuantityModal(db, self.product))


class BuyQuantityModal(Modal):
    def __init__(self, db, product):
        super().__init__(title="Buy Quantity")
        self.buy_quantity = InputText(label="Quantity",
                                      placeholder="1",
                                      custom_id="quantity", )
        self.add_item(self.buy_quantity)
        self.db = db
        self.product = product

    async def callback(self, interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel.id)
        channel_name = bot.get_channel(interaction.channel.id)
        user_id = str(interaction.user.id)
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            try:
                buy_quantity = int(self.buy_quantity.value)
            except Exception as e:
                description = "```❌ Quantity must be entered numerically.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'BuyQuantityModal price error: {e}')
                return

            cursor.execute(
                query.select_guild_product(),
                (guild_id, self.product.get('id'),)
            )
            product = cursor.fetchone()

            if product:
                price = int(product.get('price'))
            else:
                description = "```❌ There was a problem applying for the item.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'BuyQuantityModal price error: There was a problem applying for the item.')
                return

            cursor.execute(
                query.select_guild_user_points(),
                (guild_id, user_id,)
            )
            user = cursor.fetchone()

            if user:
                user_points = int(user.get('points'))
            else:
                user_points = 0

            if user_points < (price * buy_quantity):
                description = "```❌ Not enough points.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'BuyQuantityModal price error: Not enough points.')
                return
            else:
                loop = buy_quantity
                while loop > 0:
                    before_user_point = user_points
                    user_points -= price

                    cursor.execute(
                        query.insert_guild_user_ticket(),
                        (user_id, product.get('id'), guild_id,)
                    )
                    cursor.execute(
                        query.update_guild_user_point(),
                        (user_points, guild_id, user_id,)
                    )
                    cursor.execute(
                        query.insert_guild_user_point_logs(),
                        (guild_id, user_id, price * (-1),
                         before_user_point, user_points, 'item-buy', user_id,
                         channel_id, channel_name)
                    )
                    loop -= 1

                description = f"You applied for the `[{self.product.get('item_type')}]{self.product.get('name')}` x{buy_quantity} item."
                embed = make_embed({
                    'title': '✅ Item buy completed',
                    'description': description,
                    'color': 0xFFFFFF,
                })
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )
            connection.commit()
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'BuyQuantityModal db error: {e}')
        finally:
            cursor.close()
            connection.close()


class AddItemButton(View):
    def __init__(self):
        super().__init__()

    @button(label="RAFFLE", style=discord.ButtonStyle.green, custom_id="raffle_item_button")
    async def button_raffle_item(self, _, interaction):
        await interaction.response.send_modal(modal=AddItemModal(db, 'RAFFLE'))

    @button(label="FCFS", style=discord.ButtonStyle.danger, custom_id="fcfs_item_button")
    async def button_fcfs_item(self, _, interaction):
        await interaction.response.send_modal(modal=AddItemModal(db, 'FCFS'))


class AddItemModal(Modal):
    def __init__(self, db, item_type):
        super().__init__(title=f"Add {item_type} Item")
        self.item_type = item_type
        self.item_name = InputText(label="Item Name",
                                   placeholder="Example Item",
                                   custom_id="name",
                                   max_length=50, )
        self.item_image = InputText(label="Image URL",
                                    placeholder="https://example.com/image.jpg",
                                    custom_id="image", )
        self.item_price = InputText(label="Price",
                                    placeholder="100",
                                    custom_id="price", )
        self.item_quantity = InputText(label="Quantity",
                                       placeholder="1",
                                       custom_id="quantity", )
        self.add_item(self.item_name)
        self.add_item(self.item_image)
        self.add_item(self.item_price)
        self.add_item(self.item_quantity)
        self.db = db

    async def callback(self, interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                query.select_guild_store_round(),
                (guild_id,)
            )
            store = cursor.fetchone()

            if not store:
                description = "```❌ Store Setting has not yet.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal empty store error: Store Setting has not yet')
                return

            if store.get('round_status') != 'OPEN':
                description = "```❌ No rounds have been opened in the store yet.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal round_status error: No rounds have been opened in the store yet.')
                return

            name = self.item_name.value
            max_round = store.get('max_round')
            cursor.execute(
                query.select_guild_product_count(),
                (guild_id, max_round, name, )
            )
            item = cursor.fetchone()
            if int(item.get('cnt', 0)) > 0:
                description = "```❌ You already have a item with the same name.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal name error: Already have a item with the same name.')
                return

            try:
                image = self.item_image.value
                response = requests.head(image)
                if response.status_code == 200 and 'image' in response.headers.get('Content-Type'):
                    pass
            except Exception as e:
                description = "```❌ You must enter a valid image URL.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal image error: {e}')
                return

            try:
                price = int(self.item_price.value)
            except Exception as e:
                description = "```❌ Price must be entered numerically.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal price error: {e}')
                return

            try:
                quantity = int(self.item_quantity.value)
            except Exception as e:
                description = "```❌ Quantity must be entered numerically.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'AddItemModal quantity error: {e}')
                return

            cursor.execute(
                query.insert_guild_product(),
                (guild_id, store.get('max_round'), self.item_type, name, image, price, quantity,)
            )
            description = f"`{name}` has been registered as a item."
            embed = make_embed({
                'title': '✅ Item add complete',
                'description': description,
                'color': 0xFFFFFF,
            })
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            connection.commit()
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'AddItemModal db error: {e}')
        finally:
            cursor.close()
            connection.close()


class StoreSettingButton(View):
    def __init__(self, store):
        super().__init__()
        self.store = store

    @button(label="Change Setting", style=discord.ButtonStyle.primary, custom_id="button_change_setting")
    async def button_store_information(self, _, interaction):
        await interaction.response.send_modal(modal=StoreSettingModal(db, self.store))


class StoreSettingModal(Modal):
    def __init__(self, db, store):
        super().__init__(title="Store Setting")
        self.db = db
        self.store_title = InputText(label="Store Title",
                                     placeholder="🎁 SearchFi Store 🎁",
                                     value=store.get('title', ''),
                                     custom_id="title",
                                     max_length=100, )
        self.store_description = InputText(label="Store Description",
                                           placeholder="This is a SearchFi Store.",
                                           value=store.get('description', ''),
                                           custom_id="description",
                                           max_length=4000,
                                           style=InputTextStyle.multiline)
        self.store_image_url = InputText(label="Store Image URL",
                                         placeholder="https://example.com/image.jpg",
                                         value=store.get('image_url', ''),
                                         custom_id="image_url", )
        self.store_round = InputText(label="Store Round",
                                     placeholder="1",
                                     value=store.get('max_round', ''),
                                     custom_id="round", )
        self.add_item(self.store_title)
        self.add_item(self.store_description)
        self.add_item(self.store_image_url)
        self.add_item(self.store_round)

    async def callback(self, interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_guild_store_round(),
                (guild_id,)
            )
            store = cursor.fetchone()

            store_title = self.store_title.value
            store_description = self.store_description.value

            try:
                store_image_url = self.store_image_url.value
                response = requests.head(store_image_url)
                if response.status_code == 200 and 'image' in response.headers.get('Content-Type'):
                    pass
            except Exception as e:
                description = "```❌ You must enter a valid image URL.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'StoreSettingModal image error: {e}')
                return

            try:
                store_round = int(self.store_round.value)
            except Exception as e:
                description = "```❌ Round must be entered numerically.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'StoreSettingModal Round error: {e}')
                return

            if store:
                if store.get('round_status') == 'OPEN':
                    description = "```❌ Round cannot be modified as the prize draw is still in progress.```"
                    await interaction.response.send_message(description, ephemeral=True)
                    logger.error(f'StoreSettingModal round_status error')
                    return

                next_round = int(store.get('max_round')) + 1
                if store_round != next_round:
                    description = f"```❌ Next round is {next_round}round.```"
                    await interaction.response.send_message(description, ephemeral=True)
                    logger.error(f'StoreSettingModal next_round error')
                    return
            else:
                if store_round > 1:
                    description = "```❌ The first round can start at 1.```"
                    await interaction.response.send_message(description, ephemeral=True)
                    logger.error(f'StoreSettingModal First Round error')
                    return

            if store:
                cursor.execute(
                    query.update_guild_store(),
                    (store_title, store_description, store_image_url, guild_id,)
                )
            else:
                cursor.execute(
                    query.insert_guild_store(),
                    (guild_id, store_title, store_description, store_image_url,)
                )

            cursor.execute(
                query.insert_guild_store_round(),
                (guild_id, store_round, 'OPEN',)
            )

            description = f"Store information has been saved."
            embed = make_embed({
                'title': '✅ Store save complete',
                'description': description,
                'color': 0xFFFFFF,
            })
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            connection.commit()
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'StoreSettingModal db error: {e}')
        finally:
            cursor.close()
            connection.close()


class RaffleCog(commands.Cog):

    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.guild_id = None
        self.action_type = 'BOT-AUTO'
        self.action_user_id = self.bot.user.id
        self.event_announce_channel = 0
        self.hour = 20
        self.minute = 0
        self.auto_raffle_status = 'OFF'
        self.auto_raffle.start()

    def cog_unload(self):
        self.auto_raffle.cancel()

    @tasks.loop(minutes=5)
    async def auto_raffle(self):
        logger.info(f'auto_raffle_status: {self.auto_raffle_status}')
        if self.auto_raffle_status == 'ON':
            result = raffle.start_raffle(self.db, self.guild_id, self.action_type, self.action_user_id)

            description = "Congratulations! " \
                          "Here is the winner list of last giveaway\n\n"
            for product, users in result.items():
                users_str = '\n'.join([f"<@{user}>" for user in users])
                description += f"🏆 `{product}` winner:\n{users_str}\n\n"

            embed = make_embed({
                'title': '🎉 Giveaway Winner 🎉',
                'description': description,
                'color': 0xFFFFFF,
            })

            channel = self.bot.get_channel(int(self.event_announce_channel))
            await channel.send(embed=embed)

    @auto_raffle.before_loop
    async def before_auto_raffle(self):
        self.guild_id = os.getenv('GUILD_ID')
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_guild_store(),
                (self.guild_id,)
            )
            store = cursor.fetchone()

            self.hour = store.get('raffle_time_hour')
            self.minute = store.get('raffle_time_minute')
            self.action_user_id = store.get('raffle_bot_user_id', self.bot.user.id)
            self.event_announce_channel = store.get('raffle_announce_channel')
            self.auto_raffle_status = store.get('auto_raffle_status')

        except Exception as e:
            logger.error(f'before_auto_raffle error: {e}')
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

        now = datetime.datetime.now()
        next_run = datetime.datetime(now.year, now.month, now.day, int(self.hour), int(self.minute))
        delta = next_run - now

        if delta.total_seconds() > 0:
            await asyncio.sleep(delta.total_seconds())

    @commands.command(
        name='start-auto-raffle'
    )
    async def start_auto_raffle(self, ctx):
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.update_guild_store_raffle(),
                ('ON', self.guild_id,)
            )
            connection.commit()

            embed = make_embed({
                'title': 'Auto Raffle Start',
                'description': '✅ Auto raffle started.',
                'color': 0xFFFFFF,
            })
            await ctx.reply(embed=embed, mention_author=True)
        except Exception as e:
            logger.error(f'start_auto_raffle error: {e}')
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

    @commands.command(
        name='stop-auto-raffle'
    )
    async def stop_auto_raffle(self, ctx):
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.update_guild_store_raffle(),
                ('OFF', self.guild_id,)
            )
            connection.commit()

            embed = make_embed({
                'title': 'Auto Raffle Stop',
                'description': '✅ Auto raffle stopped.',
                'color': 0xff0000,
            })
            await ctx.reply(embed=embed, mention_author=True)
        except Exception as e:
            logger.error(f'stop_auto_raffle error: {e}')
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

    @commands.command(name='set-auto-raffle-interval')
    async def set_auto_raffle_interval(self, ctx, hours: int):
        self.auto_raffle.change_interval(hours=hours)
        embed = make_embed({
            'title': 'Set Auto Raffle Interval',
            'description': f'✅ Auto raffle interval set to {hours} hours.',
            'color': 0xff0000,
        })
        await ctx.reply(embed=embed, mention_author=True)


class ClaimPointButton(View):
    def __init__(self, db):
        super().__init__(timeout=None)
        self.db = db

    @button(label="Claim", style=discord.ButtonStyle.green, custom_id="claim_point_button")
    async def button_claim_point(self, _, interaction: Interaction):
        global level_reset_status

        if level_reset_status:
            description = "```❌ A reset is already in progress.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'ClaimPointButton error: {description}')
            return

        guild_id = str(interaction.guild_id)
        user = interaction.user
        user_id = str(user.id)
        action_type = 'level-role-claim'
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.select_last_reset_end_time(),
                (guild_id,)
            )
            last_reset_end_time = cursor.fetchone()

            cursor.execute(
                query.select_guild_user_roles_claim_point(),
                (guild_id,)
            )
            roles_claim_points = cursor.fetchall()
            point_by_role = {role_claim_point['role_name']: role_claim_point['point'] for role_claim_point in roles_claim_points}
            description = ""
            total_count = 0
            claim_count = 0
            claim_sum = 0

            if last_reset_end_time:
                for role in user.roles:
                    role_name = str(role.name)
                    if point_by_role.get(role_name):
                        cursor.execute(
                            query.select_guild_user_claim_role(),
                            (guild_id, user_id, role_name, last_reset_end_time.get('reset_end_time'))
                        )
                        last_claim_role = cursor.fetchone()

                        if last_claim_role:
                            description += f"`{role.name}` claim has already been claimed. -> `+0` Added.\n"
                        else:
                            cursor.execute(
                                query.insert_guild_user_claim_role(),
                                (guild_id, user_id, role_name,)
                            )

                            point = point_by_role[role_name]
                            action_user_id = user_id
                            channel_id = interaction.channel_id
                            channel_name = bot.get_channel(interaction.channel_id)

                            await save_point_and_log(cursor, guild_id, user_id, point,
                                                     action_type, action_user_id,
                                                     channel_id, channel_name)

                            connection.commit()

                            description += f"`{role.name}` claim completed. -> `+{point}` Added.\n"
                            claim_count += 1
                            claim_sum += point
                        total_count += 1

                if claim_count > 0:
                    description += f"\n All Roles claim completed."
                    embed = make_embed({
                        'title': f'✅ Role Claim Complete. Total `+{claim_sum}` Added.',
                        'description': description,
                        'color': 0xFFFFFF,
                    })
                else:
                    description += f"\n You don`t have role in claim."
                    embed = make_embed({
                        'title': '❌ Role Claim Failed',
                        'description': description,
                        'color': 0xff0000,
                    })
            else:
                description += f"\n There is no record of resetting roles.\nplease contact administrator."
                embed = make_embed({
                    'title': '❌ Role Claim Failed',
                    'description': description,
                    'color': 0xff0000,
                })

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            connection.commit()
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_claim_point db error: {e}')
        finally:
            cursor.close()
            connection.close()


class LevelRoleButtons(View):
    def __init__(self, db):
        super().__init__(timeout=None)
        self.db = db

    @button(label="Role Add", style=discord.ButtonStyle.green, custom_id="role_add_button")
    async def button_role_add(self, _, interaction: Interaction):
        await interaction.response.send_modal(modal=EditRoleModal(db, {}, interaction))

    @button(label="Role Edit", style=discord.ButtonStyle.primary, custom_id="role_edit_button")
    async def button_role_edit(self, _, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                query.select_guild_user_roles_claim_point(),
                (guild_id,)
            )
            roles = cursor.fetchall()

            await interaction.response.send_message(
                content="Select the target you want to edit.",
                view=LevelRoleSelectView(self.db, roles, 'edit', interaction),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f'button_role_edit error: {e}')
            connection.rollback()
        finally:
            cursor.close()
            connection.close()

    @button(label="Role Delete", style=discord.ButtonStyle.danger, custom_id="role_delete_button")
    async def button_role_delete(self, _, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                query.select_guild_user_roles_claim_point(),
                (guild_id,)
            )
            roles = cursor.fetchall()

            await interaction.response.send_message(
                content="Select the target you want to delete.",
                view=LevelRoleSelectView(self.db, roles, 'delete', interaction),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f'button_role_delete error: {e}')
            connection.rollback()
        finally:
            cursor.close()
            connection.close()


class LevelRoleSelectView(View):
    def __init__(self, db, roles, action_type, org_interaction):
        super().__init__()
        self.db = db
        self.roles = roles
        self.action_type = action_type
        self.org_interaction = org_interaction
        self.options = [discord.SelectOption(
            label=f"""{role.get('role_name')}""",
            value=str(role.get('id')),
            description=f"""Point: {role.get('point')}""",
        ) for role in roles]
        self.add_item(LevelRoleSelect(self.db, self.options, self.roles, self.action_type, self.org_interaction))


class LevelRoleSelect(Select):
    def __init__(self, db, options, roles, action_type, org_interaction):
        super().__init__(placeholder='Please choose a role', min_values=1, max_values=1, options=options)
        self.db = db
        self.roles = roles
        self.action_type = action_type
        self.org_interaction = org_interaction

    async def callback(self, interaction: Interaction):
        guild_id = str(interaction.guild.id)
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            if self.action_type == "delete":
                for role in self.roles:
                    if str(role.get('id')) == str(self.values[0]):
                        description = f"Do you want me to delete the `{role.get('role_name')}` role?"
                        embed = make_embed({
                            'title': 'ℹ️ Delete Confirm',
                            'description': description,
                            'color': 0xFFFFFF,
                        })
                        view = DeleteRoleButton(self.db, role, interaction)

                        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

                        await self.org_interaction.delete_original_response()
            else:
                for role in self.roles:
                    if str(role.get('id')) == str(self.values[0]):
                        await interaction.response.send_modal(modal=EditRoleModal(db, role, interaction))
        except Exception as e:
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'LevelRoleSelect error: {e}')
        finally:
            cursor.close()
            connection.close()


class EditRoleModal(Modal):
    def __init__(self, db, role, org_interaction):
        super().__init__(title="Role Add/Edit")
        self.role_name = InputText(label="Role Name",
                                   value=f"{role.get('role_name', '')}",
                                   placeholder="input a role name.",
                                   custom_id="role_name", )
        self.point = InputText(label="Point",
                               value=f"{role.get('point', '')}",
                               placeholder="input a point.",
                               custom_id="point", )
        self.add_item(self.role_name)
        self.add_item(self.point)
        self.db = db
        self.role = role
        self.org_interaction = org_interaction

    async def callback(self, interaction):
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            guild_id = self.role.get('guild_id', str(interaction.guild_id))
            role_id = self.role.get('id', None)
            role_name = self.role_name.value

            try:
                point = int(self.point.value)
            except Exception as e:
                description = "```❌ Quantity must be entered numerically.```"
                await interaction.response.send_message(description, ephemeral=True)
                logger.error(f'EditRoleModal point error: {description}')
                return

            if role_id:
                cursor.execute(
                    query.update_guild_user_roles_claim_point(),
                    (role_name, point, guild_id, role_id,)
                )

                connection.commit()

                description = f"`{role_name}` role edit completed."
                embed = make_embed({
                    'title': '✅ Role Edit Complete',
                    'description': description,
                    'color': 0xFFFFFF,
                })
            else:
                cursor.execute(
                    query.insert_guild_user_roles_claim_point(),
                    (guild_id, role_name, point,)
                )

                connection.commit()

                description = f"`{role_name}` role add completed."
                embed = make_embed({
                    'title': '✅ Role Add Complete',
                    'description': description,
                    'color': 0xFFFFFF,
                })

            await interaction.response.defer(ephemeral=True)

            await self.org_interaction.edit_original_response(
                embed=embed,
                view=None
            )
        except Exception as e:
            connection.rollback()
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'EditRoleModal db error: {e}')
        finally:
            cursor.close()
            connection.close()


class DeleteRoleButton(View):
    def __init__(self, db, role, org_interaction):
        super().__init__(timeout=None)
        self.db = db
        self.role = role
        self.org_interaction = org_interaction

    @button(label="Delete", style=discord.ButtonStyle.danger, custom_id="real_role_delete_button")
    async def button_real_role_delete(self, _, interaction: Interaction):
        guild_id = str(interaction.guild.id)
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                query.delete_guild_user_roles_claim_point(),
                (guild_id, self.role.get('id'))
            )

            connection.commit()

            description = f"`{self.role.get('role_name')}` delete completed."
            embed = make_embed({
                'title': '✅ Delete Complete',
                'description': description,
                'color': 0xFFFFFF,
            })

            await interaction.response.defer(ephemeral=True)

            await self.org_interaction.edit_original_response(
                embed=embed,
                view=None
            )
        except Exception as e:
            description = "```❌ There was a problem processing the data.```"
            await interaction.response.send_message(description, ephemeral=True)
            logger.error(f'button_real_role_delete error: {e}')
        finally:
            cursor.close()
            connection.close()


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


async def save_point_and_log(cursor, guild_id, user_id, point,
                             action_type, action_user_id,
                             channel_id, channel_name):
    cursor.execute(
        query.select_guild_user_points(),
        (guild_id, user_id,)
    )
    user = cursor.fetchone()

    if user:
        before_user_points = user.get('points')
        user_points = int(before_user_points)
        user_points += point

        if user_points < 0:
            user_points = 0

        cursor.execute(
            query.update_guild_user_point(),
            (user_points, guild_id, user_id,)
        )
    else:
        before_user_points = 0
        user_points = point

        cursor.execute(
            query.insert_guild_user_point(),
            (guild_id, user_id, user_points,)
        )

    cursor.execute(
        query.insert_guild_user_point_logs(),
        (guild_id, user_id, point,
         before_user_points, user_points, action_type, action_user_id,
         channel_id, channel_name)
    )

    return before_user_points, user_points


async def store_setting(ctx):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()
    store = {}
    try:
        cursor.execute(
            query.select_guild_store_round(),
            (guild_id,)
        )
        store = cursor.fetchone()
    except Exception as e:
        logger.error(f'store_setting db error: {e}')
    finally:
        cursor.close()
        connection.close()

    description = f"⚙️ Press the `Change Setting` button to setting the store.\n\n"
    embed = make_embed({
        'title': 'Current Store Setting Information',
        'description': description,
        'color': 0xFFFFFF,
    })

    if store:
        embed.add_field(name="Store Title", value=store.get('title', 'Not yet.'), inline=False)
        embed.add_field(name="Store Description", value=f"```{store.get('description', 'Not yet.')}```", inline=False)
        embed.add_field(name="Store Round", value=f"{store.get('max_round', 'Not yet.')} "
                                                  f"({store.get('round_status', 'Not yet')})", inline=False)
        embed.add_field(name="Store Image URL", value="")
        embed.set_image(url=store.get('image_url', 'Not yet.'))
    else:
        store = {
            'title': None,
            'description': None,
            'max_round': None,
            'round_status': None,
            'image_url': None,
        }

    view = StoreSettingButton(store)
    await ctx.reply(embed=embed, view=view, mention_author=True)


async def store_main(ctx):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            query.select_guild_store_round(),
            (guild_id,)
        )
        store = cursor.fetchone()

        cursor.execute(
            query.select_guild_products(),
            (guild_id,)
        )
        products = cursor.fetchall()

        if not store:
            store = {
                'title': '🎁 SearchFi Store 🎁',
                'description': 'This is SearchFi Store!',
                'image_url': 'https://images-ext-2.discordapp.net/external/OG6ABL87frdJQcTXA5shV_LcAZAmEv-vn9GUsx3TXrg/%3Fraw%3Dtrue/https/github.com/vmpyre/BotsOnDisplay/blob/main/twitter%2520activity%2520rewards/Blue%2520Modern%2520Futuristic%2520Desktop%2520Wallpaper%2520%282%29.gif?width=2022&height=1138',
                'max_round': 0,
            }

        if store.get('round_status') != 'OPEN':
            description = "```❌ No rounds have been opened in the store yet.```"
            await ctx.reply(description, mention_author=True)
            logger.error(f'store_main error: No rounds have been opened in the store yet.')
            return

        embed = make_embed({
            'title': store.get('title'),
            'description': store.get('description'),
            'color': 0xFFFFFF,
            'image_url': store.get('image_url'),
        })

        items = ""
        for product in products:
            items += f"`[{product.get('item_type')}]{product.get('name')}` x{product.get('quantity')}\n"

        embed.add_field(name=f"Store Items", value=items)

        view = WelcomeView(db)
        await ctx.send(embed=embed, view=view)
    except Exception as e:
        description = "```❌ There was a problem processing the data.```"
        await ctx.reply(description, mention_author=True)
        logger.error(f'store_main error: {e}')
    finally:
        cursor.close()
        connection.close()


async def add_item(ctx):
    description = "🎁️ Press the `RAFFLE` or `FCFS` button to register the item."
    embed = make_embed({
        'title': 'Add Item',
        'description': description,
        'color': 0xFFFFFF,
    })
    view = AddItemButton()
    await ctx.reply(embed=embed, view=view, mention_author=True)


async def give_rewards(ctx, user_tag, amount):
    try:
        params = {
            'user_id': user_tag[2:-1],
            'point': int(amount),
            'action_user_id': ctx.author.id,
            'action_type': 'give-rewards',
        }

        result = await save_rewards(ctx, params)

        if result.get('success') > 0:
            description = f"Successfully gave `{params.get('point')}` points to {user_tag}\n\n" \
                          f"{user_tag} points: `{result.get('before_user_points')}` -> `{result.get('after_user_points')}`"
            embed = make_embed({
                'title': '✅ Point Given',
                'description': description,
                'color': 0xFFFFFF,
            })
            await ctx.reply(embed=embed, mention_author=True)
    except Exception as e:
        logger.error(f'give_rewards error: {e}')


async def remove_rewards(ctx, user_tag, amount):
    try:
        params = {
            'user_id': user_tag[2:-1],
            'point': int(amount) * (-1),
            'action_user_id': ctx.author.id,
            'action_type': 'remove-rewards',
        }

        result = await save_rewards(ctx, params)

        if result.get('success') > 0:
            description = f"Successfully removed `{params.get('point')}` points to {user_tag}\n\n" \
                          f"{user_tag} points: `{result.get('before_user_points')}` -> `{result.get('after_user_points')}`"
            embed = make_embed({
                'title': '✅ Point Removed',
                'description': description,
                'color': 0xFFFFFF,
            })
            await ctx.reply(embed=embed, mention_author=True)
    except Exception as e:
        logger.error(f'remove_rewards error: {e}')


async def give_role_rewards(ctx, role: Union[Role, int, str], amount):
    # 입력값이 롤 객체인 경우
    if isinstance(role, discord.Role):
        role_found = role
    # 입력값이 역할 ID인 경우
    elif isinstance(role, int):
        role_found = discord.utils.get(ctx.guild.roles, id=role)
    # 입력값이 역할 이름인 경우
    else:
        role_found = discord.utils.get(ctx.guild.roles, name=role)

    if role_found is None:
        embed = Embed(title="Error",
                      description=f"❌ Role not found for name, ID, or mention {role}. Please enter a valid role name, ID, or mention.\n\n",
                      color=0xff0000)
        await ctx.reply(embed=embed, mention_author=True)
        return

    role_id = role_found.id
    all_users = ctx.guild.members
    total_count = len(all_users)
    processed_count = 0

    for user in all_users:
        try:
            for role in user.roles:
                if role.id == role_id:
                    params = {
                        'user_id': str(user.id),
                        'point': int(amount),
                        'action_user_id': ctx.author.id,
                        'action_type': 'give-role-rewards',
                    }
                    await save_rewards(ctx, params)
            processed_count += 1
        except Exception as e:
            logger.error(f"{user.id} - {user.name} - {e}")
            await ctx.send(f"{user.id} - {user.name} - {e}")

        # 10000명마다 진행률 확인
        if processed_count % 10000 == 0 or processed_count == total_count:
            await ctx.send(f"progress: {processed_count}/{total_count} ({(processed_count / total_count) * 100:.2f}%)")

    description = f"Successfully gave `{amount}` points to `{role_found.name}` role users."
    embed = make_embed({
        'title': '✅ Role Point Given',
        'description': description,
        'color': 0xFFFFFF,
    })
    await ctx.reply(embed=embed, mention_author=True)


async def save_rewards(ctx, params):
    guild_id = str(ctx.guild.id)
    channel_id = str(ctx.channel.id)
    channel_name = bot.get_channel(ctx.channel.id)
    connection = db.get_connection()
    cursor = connection.cursor()
    result = 0
    try:
        user_id = params.get('user_id')
        point = params.get('point')
        action_user_id = params.get('action_user_id')
        action_type = params.get('action_type')

        before_user_points, user_points = await save_point_and_log(cursor, guild_id, user_id, point,
                                                                   action_type, action_user_id,
                                                                   channel_id, channel_name)

        connection.commit()
        result = {
            'success': 1,
            'before_user_points': before_user_points,
            'after_user_points': user_points
        }
    except Exception as e:
        logger.error(f'save_rewards error: {e}')
        connection.rollback()
        result = {
            'success': 0,
            'before_user_points': 0,
            'after_user_points': 0
        }
    finally:
        cursor.close()
        connection.close()
        return result


async def giveaway_raffle(ctx):
    guild_id = str(ctx.guild.id)
    action_type = 'USER-MANUAL'
    action_user_id = ctx.author.id
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            query.select_guild_store(),
            (guild_id,)
        )
        store = cursor.fetchone()

        event_announce_channel = store.get('raffle_announce_channel')

        if not event_announce_channel:
            event_announce_channel = ctx.channel.id

        result_raffle = raffle.start_raffle(db, guild_id, action_type, action_user_id)
        result_fcfs = raffle.start_fcfs(db, guild_id, action_type, action_user_id)

        description = "Congratulations! " \
                      "here is the winner list of last giveaway\n\n"
        for product, users in result_raffle.items():
            users_str = '\n'.join([f"{user.mention}" for user in users])
            description = f"🏆 `{product}` winner:\n{users_str}\n\n"

            embed = make_embed({
                'title': f'🎉 Giveaway `{product}` Raffle Winner 🎉',
                'description': description,
                'color': 0xFFFFFF,
            })

            channel = bot.get_channel(int(event_announce_channel))
            await channel.send(embed=embed)

        for product, users in result_fcfs.items():
            users_str = '\n'.join([f"{user.mention}" for user in users])
            description = f"🏆 `{product}` winner:\n{users_str}\n\n"

            embed = make_embed({
                'title': f'🎉 Giveaway `{product}` FCFS Winner 🎉',
                'description': description,
                'color': 0xFFFFFF,
            })

            channel = bot.get_channel(int(event_announce_channel))
            await channel.send(embed=embed)

        description = f"Check it out on the <#{int(event_announce_channel)}> channel."
        embed = make_embed({
            'title': 'Giveaway Raffle Complete',
            'description': description,
            'color': 0xFFFFFF,
        })
        await ctx.reply(embed=embed, mention_author=True)
    except Exception as e:
        logger.error(f'giveaway_raffle error: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


async def today_self_rewards(ctx, today_self_rewards_amount):
    guild_id = str(ctx.guild.id)
    channel_id = str(ctx.channel.id)
    channel_name = bot.get_channel(ctx.channel.id)
    action_type = 'today-self-rewards'
    action_user_id = ctx.author.id
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            query.select_today_self_rewards(),
            (guild_id, action_user_id, action_type)
        )
        last_date = cursor.fetchone()['last_self_rewards']

        # 유저가 오늘 이미 출석을 한 경우 에러 메시지 보내기
        if last_date and last_date.strftime('%Y-%m-%d') == datetime.datetime.now().date().strftime('%Y-%m-%d'):
            await ctx.reply("You've already done it. Please try again tomorrow.", mention_author=True)
            return

        await save_point_and_log(cursor, guild_id, action_user_id, today_self_rewards_amount,
                                 action_type, action_user_id,
                                 channel_id, channel_name)

        connection.commit()

        await ctx.reply(f"`+{today_self_rewards_amount}` Added", mention_author=True)

    except Exception as e:
        logger.error(f'today_self_rewards error: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


async def level_rewards(ctx):
    description = "💎 Claim if you have an Level Role!"
    embed = make_embed({
        'title': 'Point Claim by Level',
        'description': description,
        'color': 0xFFFFFF,
    })
    view = ClaimPointButton(db)
    await ctx.reply(embed=embed, view=view, mention_author=True)


async def level_reset(ctx):
    global level_reset_status

    if level_reset_status:
        description = "```❌ A reset is already in progress.```"
        await ctx.reply(description, mention_author=True)
        logger.error(f'level_reset error: {description}')
        return

    guild_id = str(ctx.guild.id)
    action_type = 'level-role-point-reset'
    action_user_id = ctx.author.id
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        level_reset_status = True

        all_users = ctx.guild.members

        cursor.execute(
            query.select_guild_user_roles_claim_point(),
            (guild_id,)
        )
        roles_claim_points = cursor.fetchall()
        point_by_role = {role_claim_point['role_name']: role_claim_point['point'] for role_claim_point in roles_claim_points}

        # 초기화 시작 로그 기록
        cursor.execute(
            query.insert_guild_user_roles_reset(),
            (guild_id, action_user_id,)
        )

        connection.commit()

        # 초기화 로그 ID
        reset_id = cursor.lastrowid
        reset_count = 0

        total_count = len(all_users)

        for user in all_users:
            # if not (str(user.id) == "732448005180883017" or str(user.id) == "952546993878741072"):
            #     print(f"{user.name} -> no reset target!")
            #     continue

            user_id = user.id
            logger.info(f"{user.name} -> reset start!")

            # user의 level role 초기화
            for role in user.roles:
                role_name = str(role.name)
                if point_by_role.get(role_name):
                    await user.remove_roles(role)
                    logger.info(f"{user.name} -> {role_name} role delete.")

            # user의 point 초기화
            channel_id = ctx.channel.id
            channel_name = bot.get_channel(ctx.channel.id)

            cursor.execute(
                query.select_guild_user_points(),
                (guild_id, user_id,)
            )
            user = cursor.fetchone()

            if user:
                before_user_points = int(user.get('points'))
                point = -before_user_points
                user_points = before_user_points + point

                cursor.execute(
                    query.update_guild_user_point(),
                    (user_points, guild_id, user_id,)
                )

                cursor.execute(
                    query.insert_guild_user_point_logs(),
                    (guild_id, user_id, point,
                     before_user_points, user_points, action_type, action_user_id,
                     channel_id, channel_name)
                )

                connection.commit()

            reset_count += 1

            # 10000명마다 진행률 확인
            if reset_count % 10000 == 0 or reset_count == total_count:
                await ctx.send(f"progress: {reset_count}/{total_count} ({(reset_count / total_count) * 100:.2f}%)")

        # 초기화 종료 로그 기록
        cursor.execute(
            query.update_guild_user_roles_reset(),
            (action_user_id, reset_count, reset_id,)
        )

        connection.commit()

        description = f"Level Reset completed."
        embed = make_embed({
            'title': '✅ Level Reset',
            'description': description,
            'color': 0xFFFFFF,
        })
        await ctx.reply(embed=embed, mention_author=True)

    except Exception as e:
        logger.error(f'level_reset error: {e}')
        connection.rollback()
    finally:
        level_reset_status = False
        cursor.close()
        connection.close()


async def level_list(ctx):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            query.select_guild_user_roles_claim_point(),
            (guild_id,)
        )
        roles = cursor.fetchall()

        if roles:
            header = "```\n{:<15}{:>10}\n".format("Level Role Name", "Point")
            line = "-" * (15 + 10) + "\n"  # 각 열의 너비 합만큼 하이픈 추가
            description = header + line
            for role in roles:
                description += "{:<15}{:>10}\n".format(role.get('role_name'), role.get('point'))
            description += "```"
            embed = make_embed({
                'title': 'Level Role List',
                'description': description,
                'color': 0xFFFFFF,
            })
            view = LevelRoleButtons(db)
            await ctx.reply(embed=embed, view=view, mention_author=True)
        else:
            description = "```❌ No level role list.```"
            view = LevelRoleButtons(db)
            await ctx.reply(description, view=view, mention_author=True)
            logger.error(f'level_list error: {description}')

    except Exception as e:
        logger.error(f'level_list error: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


async def give_alpha_call_rewards(guild_id, call_channel_id, announce_channel_id):
    connection = db.get_connection()
    cursor = connection.cursor()

    try:
        # 특정 채널의 메시지 검사
        guild = bot.get_guild(guild_id)
        call_channel = guild.get_channel(call_channel_id)
        announce_channel = guild.get_channel(announce_channel_id)
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        messages = await call_channel.history(after=yesterday).flatten()

        user_points = {}
        for message in messages:
            # 봇이 작성한 메시지는 무시
            if message.author.bot:
                continue
            user_id = message.author.id
            if user_id not in user_points:
                user_points[user_id] = 0
            user_points[user_id] += 50
            if user_points[user_id] > 200:
                user_points[user_id] = 200

        # 포인트 부여 및 로그 저장
        action_type = 'alpha-call-rewards'
        action_user_id = bot.user.id
        channel_id = call_channel_id
        channel_name = bot.get_channel(channel_id)
        for user_id, point in user_points.items():
            user = guild.get_member(user_id)
            before_user_points, user_points = await save_point_and_log(cursor, guild_id, user_id, point,
                                                                       action_type, action_user_id,
                                                                       channel_id, channel_name)
            connection.commit()

            description = f"Successfully gave `{point}` points to {user.mention}\n\n" \
                          f"{user.mention} points: `{before_user_points}` -> `{user_points}`"
            embed = make_embed({
                'title': '✅ AlphaCall Point Given',
                'description': description,
                'color': 0xFFFFFF,
            })
            await announce_channel.send(embed=embed, mention_author=True)
    except Exception as e:
        logger.error(f'give_alpha_call_rewards error: {e}')
        connection.rollback()
    finally:
        cursor.close()
        connection.close()


async def bulk_role(ctx, channel: Union[discord.TextChannel, discord.Thread, int, str], role: Union[discord.Role, int, str]):
    # 입력값이 롤 객체인 경우
    if isinstance(role, discord.Role):
        role_found = role
    # 입력값이 역할 ID인 경우
    elif isinstance(role, int):
        role_found = discord.utils.get(ctx.guild.roles, id=role)
    # 입력값이 역할 이름인 경우
    else:
        role_found = discord.utils.get(ctx.guild.roles, name=role)

    if role_found is None:
        embed = Embed(title="Error",
                      description=f"❌ Role not found for name, [ID, or mention {role}. Please enter a valid role name, ID, or mention.\n\n"
                                  f"❌ {role} 이름, ID 또는 멘션의 역할을 찾을 수 없습니다. 올바른 역할 이름, ID 또는 멘션을 입력해주세요.",
                      color=0xff0000)
        await ctx.reply(embed=embed, mention_author=True)
        return

    # 입력값이 채널 객체인 경우
    if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.Thread):
        channel_found = channel
    # 입력값이 채널 ID인 경우
    elif isinstance(channel, int):
        channel_found = discord.utils.get(ctx.guild.channels, id=channel)
    # 입력값이 채널 이름인 경우
    else:
        channel_found = discord.utils.get(ctx.guild.channels, name=channel)

    if channel_found is None:
        embed = Embed(title="Error",
                      description=f"❌ Channel not found for name, ID, or mention {channel}. Please enter a valid channel name, ID, or mention.\n\n"
                                  f"❌ {channel} 이름, ID 또는 멘션의 채널을 찾을 수 없습니다. 올바른 채널 이름, ID 또는 멘션을 입력해주세요.",
                      color=0xff0000)
        await ctx.reply(embed=embed, mention_author=True)
        return

    user_ids = []
    try:
        # 스레드의 모든 메시지를 가져와 각 메시지의 작성자 ID를 수집합니다.
        async for message in channel_found.history(limit=None):
            if message.author != ctx.bot.user:  # 봇은 제외
                user_ids.append(message.author.id)

        # 수집된 사용자 ID에서 중복을 제거합니다.
        unique_user_ids = set(user_ids)

        # 각 사용자에게 역할을 부여합니다.
        for user_id in unique_user_ids:
            member = ctx.guild.get_member(user_id)
            if member is not None:
                await member.add_roles(role_found)
                await ctx.send(f"🟢 Role `{role_found.name}` has been assigned to <@{member.id}>.")

        embed = discord.Embed(title=f"{role_found.name} assigned",
                              description=f"✅ 총 {len(unique_user_ids)}명의 사용자에게 `{role_found.name}` 역할이 부여되었습니다.\n\n"
                                          f"✅ The `{role_found.name}` role has been assigned to {len(unique_user_ids)} users.",
                              color=0x00ff00)
        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f'Error: {e}')
        embed = discord.Embed(title="Error",
                              description="🔴 명령어 처리 중 오류가 발생했습니다.\n\n"
                                          "🔴 An error occurred while processing the command.",
                              color=0xff0000)
        await ctx.send(embed=embed)


@tasks.loop(minutes=1)
async def alpha_call_rewards(guild_id, call_channel_id, announce_channel_id):
    now = datetime.datetime.now()
    if now.hour == 17 and now.minute == 00:  # 한국시간 17시 00분
        logger.info(f"alpha call batch start! now time: {now}")
        await give_alpha_call_rewards(guild_id, call_channel_id, announce_channel_id)


event_role_channel_id = None
log_channel_id = None
no_xp_roles = {}


async def bulk_add_role(ctx, role: Union[Role, int, str]):
    logger.info(f"guild: {ctx.guild}")
    logger.info(f"role: {role}")


    # 입력값이 롤 객체인 경우
    if isinstance(role, Role):
        role_found = role
    # 입력값이 역할 ID인 경우
    elif isinstance(role, int):
        role_found = discord.utils.get(ctx.guild.roles, id=role)
    # 입력값이 역할 이름인 경우
    else:
        role_found = discord.utils.get(ctx.guild.roles, name=role)

    if role_found is None:
        embed = Embed(title="Error",
                      description=f"❌ Role not found for name, ID, or mention {role}. Please enter a valid role name, ID, or mention.\n\n"
                                  f"❌ {role} 이름, ID 또는 멘션의 역할을 찾을 수 없습니다. 올바른 역할 이름, ID 또는 멘션을 입력해주세요.",
                      color=0xff0000)
        await ctx.reply(embed=embed, mention_author=True)
        return

    # 컨텍스트가 스레드인지 확인
    if not isinstance(ctx.channel, discord.Thread):
        embed = discord.Embed(title="Error",
                              description="❌ 이 명령어는 스레드 내에서만 사용할 수 있습니다.\n\n"
                                          "❌ This command can only be used within a thread.",
                              color=0xff0000)
        await ctx.send(embed=embed)
        return

    # 스레드가 특정 이벤트 채널에 속하는지 확인
    if ctx.channel.parent_id != event_role_channel_id:
        embed = discord.Embed(title="Error",
                              description=f"❌ 이 스레드는 <#{event_role_channel_id}> 채널에 속하지 않습니다.\n\n"
                                          f"❌ This thread does not belong to <#{event_role_channel_id}> channel.",
                              color=0xff0000)
        await ctx.send(embed=embed)
        return

    user_ids = []
    try:
        # 스레드의 모든 메시지를 가져와 각 메시지의 작성자 ID를 수집합니다.
        async for message in ctx.channel.history(limit=None):
            if message.author != ctx.bot.user:  # 봇은 제외
                user_ids.append(message.author.id)

        # 수집된 사용자 ID에서 중복을 제거합니다.
        unique_user_ids = set(user_ids)

        # for user_id in set(user_ids):
        #     member = ctx.guild.get_member(user_id)
        #     if any(mod_role.id in no_xp_roles for mod_role in member.roles):
        #         unique_user_ids.remove(member.id)

        channel = bot.get_channel(int(log_channel_id))

        # 각 사용자에게 역할을 부여합니다.
        for user_id in unique_user_ids:
            member = ctx.guild.get_member(user_id)
            if member is not None:
                await member.add_roles(role_found)

                if channel:
                    await channel.send(f"🟢 Role `{role_found.name}` has been assigned to <@{member.id}>.")
                else:
                    await ctx.send(f"🟢 Role `{role_found.name}` has been assigned to <@{member.id}>.")

        embed = discord.Embed(title=f"{role_found.name} assigned",
                              description=f"✅ 총 {len(unique_user_ids)}명의 사용자에게 `{role_found.name}` 역할이 부여되었습니다.\n\n"
                                          f"✅ The `{role_found.name}` role has been assigned to {len(unique_user_ids)} users.",
                              color=0x00ff00)
        if channel:
            await channel.send(embed=embed)
        else:
            await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f'Error: {e}')
        embed = discord.Embed(title="Error",
                              description="🔴 명령어 처리 중 오류가 발생했습니다.\n\n"
                                          "🔴 An error occurred while processing the command.",
                              color=0xff0000)
        channel = bot.get_channel(int(log_channel_id))
        await channel.send(embed=embed)


async def export_role_members(ctx, role_input: str = None):
    # Send initial progress message
    progress_msg = await ctx.send("Starting member list extraction...")

    try:
        if role_input:
            # Single role export
            role = None
            if len(ctx.message.role_mentions) > 0:
                role = ctx.message.role_mentions[0]
            else:
                role = discord.utils.get(ctx.guild.roles, name=role_input)

            if not role:
                await progress_msg.edit(content="Could not find the specified role. Please check if the role name is correct.")
                return

            roles_to_process = [role]
            await progress_msg.edit(content=f"Extracting member list for role {role.mention}...")
        else:
            # All roles export
            roles_to_process = sorted(ctx.guild.roles[1:], key=lambda x: x.position, reverse=True)  # Exclude @everyone
            await progress_msg.edit(content="Extracting member lists for all roles...")

        # Create a folder for excel files if processing multiple roles
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        if len(roles_to_process) > 1:
            folder_name = f"role_export_{timestamp}"
            os.makedirs(folder_name, exist_ok=True)

        # Process each role
        all_files = []
        summary_data = []

        for role in roles_to_process:
            # Skip roles with no members
            if not role.members:
                continue

            # Collect member information
            members_data = []
            for member in role.members:
                member_info = {
                    'Username': member.name,
                    'User Tag': str(member),
                    'Nickname': member.nick if member.nick else member.name,
                    'User ID': str(member.id),
                    'Join Date': member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'Unknown',
                    'Account Created': member.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                members_data.append(member_info)

            # Create DataFrame
            if members_data:
                df = pd.DataFrame(members_data)

                # Add to summary data
                summary_data.append({
                    'Role Name': role.name,
                    'Member Count': len(members_data),
                    'Role Color': str(role.color),
                    'Role ID': str(role.id),
                    'Role Position': role.position
                })

                # Save to Excel
                if len(roles_to_process) > 1:
                    filename = os.path.join(folder_name, f"role_members_{role.name}_{timestamp}.xlsx")
                else:
                    filename = f"role_members_{role.name}_{timestamp}.xlsx"

                df.to_excel(filename, index=False, engine='openpyxl')
                all_files.append(filename)

        # Create summary sheet if processing multiple roles
        if len(roles_to_process) > 1:
            summary_df = pd.DataFrame(summary_data)
            summary_filename = os.path.join(folder_name, f"_summary_{timestamp}.xlsx")
            summary_df.to_excel(summary_filename, index=False, engine='openpyxl')
            all_files.append(summary_filename)

        # Send files
        if not all_files:
            await progress_msg.edit(content="No members found in the specified role(s).")
            return

        for file in all_files:
            await ctx.send(file=discord.File(file))

        # Final message
        if len(roles_to_process) > 1:
            await progress_msg.edit(content=f"Exported member lists for {len(summary_data)} roles with members.")
        else:
            await progress_msg.edit(content=f"Exported member list for role '{roles_to_process[0].name}'.")

        # Cleanup local files
        for file in all_files:
            try:
                os.remove(file)
                if len(roles_to_process) > 1:
                    os.rmdir(folder_name)
            except Exception:
                pass

    except Exception as e:
        await progress_msg.edit(content=f"An error occurred: {str(e)}")