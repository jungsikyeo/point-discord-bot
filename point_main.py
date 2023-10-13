import discord
import os
import requests
import db_pool
import db_query as query
import raffle
import datetime
import asyncio
from discord.ext import tasks, commands
from discord.interactions import Interaction
from discord.ui import View, button, Select, Modal, InputText
from discord import Embed, ButtonStyle, InputTextStyle
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
                description += f"""`{user_ticket.get('name')}`     x{user_ticket.get('tickets')}\n"""
            embed = make_embed({
                'title': f"My Tickets - {all_user_tickets[0].get('round')}Round",
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
            label=f"""{product.get('name')}""",
            value=product.get('name'),
            description=f"""Price: {product.get('price')}""",
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
                        (guild_id, user_id, price * (-1), 'item-buy', user_id)
                    )
                    loop -= 1

                description = f"You applied for the `{self.product.get('name')}` x{buy_quantity} item."
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

    @button(label="Add Item", style=discord.ButtonStyle.primary, custom_id="add_item_button")
    async def button_add_item(self, _, interaction):
        await interaction.response.send_modal(modal=AddItemModal(db))


class AddItemModal(Modal):
    def __init__(self, db):
        super().__init__(title="Add Item")
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
            cursor.execute(
                query.select_guild_product_count(),
                (guild_id, name,)
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
                (guild_id, store.get('max_round'), name, image, price, quantity,)
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

    @tasks.loop(hours=24)
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

        embed = make_embed({
            'title': store.get('title'),
            'description': store.get('description'),
            'color': 0xFFFFFF,
            'image_url': store.get('image_url'),
        })

        items = ""
        for product in products:
            items += f"`{product.get('name')}` x{product.get('quantity')}\n"

        embed.add_field(name=f"Store Items - {store.get('max_round')}Round", value=items)

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
    description = "🎁️ Press the `Add Item` button to register the item."
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


async def save_rewards(ctx, params):
    guild_id = str(ctx.guild.id)
    connection = db.get_connection()
    cursor = connection.cursor()
    result = 0
    try:
        user_id = params.get('user_id')
        point = params.get('point')
        action_user_id = params.get('action_user_id')
        action_type = params.get('action_type')

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
            (guild_id, user_id, point, action_type, action_user_id)
        )

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

        result = raffle.start_raffle(db, guild_id, action_type, action_user_id)

        description = "Congratulations! " \
                      "here is the winner list of last giveaway\n\n"
        for product, users in result.items():
            users_str = '\n'.join([f"<@{user}>" for user in users])
            description += f"🏆 `{product}` winner:\n{users_str}\n\n"

        embed = make_embed({
            'title': '🎉 Giveaway Winner 🎉',
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
