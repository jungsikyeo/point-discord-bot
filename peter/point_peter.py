import os
import sys
import logging
import discord
from discord.ui import View, button, Select, Modal, InputText
from discord import Embed, ButtonStyle, InputTextStyle
from discord.ext import commands
from typing import Union
from dotenv import load_dotenv
from discord.interactions import Interaction

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


# @bot.command(
#     name='store-setting'
# )
# @commands.has_any_role(*team_role_ids)
# async def store_setting(ctx):
#     await base_bot.store_setting(ctx)
#
#
# @bot.command(
#     name='store-main'
# )
# @commands.has_any_role(*team_role_ids)
# async def store_main(ctx):
#     await base_bot.store_main(ctx)
#
#
# @bot.command(
#     name='add-item'
# )
# @commands.has_any_role(*team_role_ids)
# async def add_item(ctx):
#     await base_bot.add_item(ctx)
#
#
# @bot.command(
#     name='give-rewards'
# )
# @commands.has_any_role(*mod_role_ids)
# async def give_rewards(ctx, user_tag, amount):
#     await base_bot.give_rewards(ctx, user_tag, amount)
#
#
# @bot.command(
#     name='remove-rewards'
# )
# @commands.has_any_role(*mod_role_ids)
# async def remove_rewards(ctx, user_tag, amount):
#     await base_bot.remove_rewards(ctx, user_tag, amount)
#
#
# @bot.command(
#     name='giveaway-raffle'
# )
# @commands.has_any_role(*mod_role_ids)
# async def giveaway_raffle(ctx):
#     await base_bot.giveaway_raffle(ctx)


@bot.command(
    name='bulk-role'
)
@commands.has_any_role(*mod_role_ids)
async def bulk_role(ctx, channel: Union[discord.TextChannel, discord.Thread, int, str], role: Union[discord.Role, int, str]):
    await base_bot.bulk_role(ctx, channel, role)


all_question = [
    {
        "Q": "question 11111???",
        "A": "A group of players who team up for raids and battles (Web2)",
        "B": "A decentralized autonomous organization (DAO) that manages in-game assets and earnings (P2E)",
    },
    {
        "Q": "What do you find more interesting in a game?",
        "A": "Exciting and novel gameplay experiences filled with new challenges and growth (Web2)",
        "B": "In-game asset accumulation through a well-designed economic system and strategic play (P2E)",
    },
    {
        "Q": "What are you looking forward to with MapleStory Universe?",
        "A": "New gameplay experiences created with the MapleStory IP (Web2, MS)",
        "B": "NFTs and decentralized assets that can be earned in MapleStory Universe (P2E)",
    },
    {
        "Q": "What are your thoughts on in-game purchases?",
        "A": "I pay for the game itself or for enjoying its content (Web2)",
        "B": "I view in-game purchases as potential investments that can generate real-world income (P2E)",
    },
    {
        "Q": "Do you have experience purchasing or investing in NFTs or tokens?",
        "A": "No or only limited experience",
        "B": "Actively investing in NFTs/tokens",
    },
    {
        "Q": "What are you most looking forward to about MapleStory N?",
        "A": "Owning items or characters as NFTs (Web3)",
        "B": "Generating new income through MapleStory N (P2E)",
    },
    {
        "Q": "What comes to mind when you hear about providing item ownership to users?",
        "A": "Items can be traded freely without restrictions (Web2)",
        "B": "Item ownership can create additional value through investment, lending, etc. (P2E)",
    },
]
view_timeout = 5 * 60


class WelcomeView(View):
    def __init__(self, db):
        super().__init__(timeout=None)
        self.db = db

    @button(label="Start", style=ButtonStyle.primary)
    async def button_start(self, _, interaction: Interaction):
        user = interaction.user
        for role in user.roles:
            if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                await interaction.response.send_message(
                    content=f"# You have already been granted {role.mention}.",
                    ephemeral=True
                )
                return

        my_selected = {
            "user_id": str(interaction.user.id),
            "A": 0,
            "B": 0,
        }

        content = f"# **1. {all_question[0].get('Q')}**\n" \
                  f"```" \
                  f"A) {all_question[0].get('A')}\n\n" \
                  f"B) {all_question[0].get('B')}" \
                  f"```"

        await interaction.response.send_message(
            content=content,
            view=QuestionSelectView(self.db, my_selected, interaction),
            ephemeral=True
        )


class QuestionSelectView(View):
    def __init__(self, db, my_selected, org_interaction: Interaction):
        super().__init__(timeout=view_timeout)
        self.db = db
        self.my_selected = my_selected
        self.org_interaction = org_interaction

    @button(label="A", style=ButtonStyle.primary)
    async def button_a(self, _, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        self.my_selected["A"] = self.my_selected["A"] + 1
        q_index = self.my_selected["A"] + self.my_selected["B"]

        if q_index > 6:
            user = interaction.user
            for role in user.roles:
                if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                    await self.org_interaction.edit_original_response(
                        content=f"# You have already been granted {role.mention}."
                    )
                    return

            if self.my_selected["A"] > self.my_selected["B"]:
                add_role = interaction.guild.get_role(int(os.getenv("A_ROLE_ID")))
                await user.add_roles(add_role)
            else:
                add_role = interaction.guild.get_role(int(os.getenv("B_ROLE_ID")))
                await user.add_roles(add_role)

            await self.org_interaction.edit_original_response(
                view=None,
                content=f"# You've been given {add_role.mention}."
            )
        else:
            content = f"# **{q_index+1}. {all_question[q_index].get('Q')}**\n" \
                      f"```" \
                      f"A) {all_question[q_index].get('A')}\n\n" \
                      f"B) {all_question[q_index].get('B')}\n" \
                      f"```"
            await self.org_interaction.edit_original_response(
                content=content,
                view=QuestionSelectView(self.db, self.my_selected, interaction),
            )

    @button(label="B", style=ButtonStyle.danger)
    async def button_b(self, _, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        self.my_selected["B"] = self.my_selected["B"] + 1
        q_index = self.my_selected["A"] + self.my_selected["B"]

        if q_index > 6:
            user = interaction.user
            for role in user.roles:
                if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                    await self.org_interaction.edit_original_response(
                        content=f"# You have already been granted {role.mention}."
                    )
                    return

            if self.my_selected["A"] > self.my_selected["B"]:
                add_role = interaction.guild.get_role(int(os.getenv("A_ROLE_ID")))
                await user.add_roles(add_role)
            else:
                add_role = interaction.guild.get_role(int(os.getenv("B_ROLE_ID")))
                await user.add_roles(add_role)

            await self.org_interaction.edit_original_response(
                view=None,
                content=f"# You've been given {add_role.mention}."
            )
        else:
            content = f"# **{q_index+1}. {all_question[q_index].get('Q')}**\n" \
                      f"```" \
                      f"A) {all_question[q_index].get('A')}\n\n" \
                      f"B) {all_question[q_index].get('B')}\n" \
                      f"```"
            await self.org_interaction.edit_original_response(
                content=content,
                view=QuestionSelectView(self.db, self.my_selected, interaction),
            )

    async def on_timeout(self):
        if self.org_interaction:
            await self.org_interaction.delete_original_response()


@bot.command(
    name='open-qna'
)
@commands.has_any_role(*mod_role_ids)
async def open_qna(ctx):
    description = "질문을 시작합니다."

    embed = Embed(title="Open Question", description=description, color=0xFFFFFF)
    view = WelcomeView(db)
    await ctx.send(embed=embed, view=view)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)
    # bot.add_cog(base_bot.RaffleCog(bot, db))


bot.run(bot_token)
