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
        "Q": "1. Which aspect of MapleStory Universe intrigues you the most?",
        "A": "(A) Ability to own and manage NFT items within the blockchain system",
        "B": "(B) Innovative gaming experiences and adventures offered by the MapleStory IP",
    },
    {
        "Q": "2. What makes you more engaged when playing a game?",
        "A": "(A) Overcoming challenges, experiencing character growth, and discovering new content",
        "B": "(B) Being part of a sophisticated economic system, where I can own non-fungible items",
    },
    {
        "Q": "3. Which feature of MapleStory N makes you most anticipating?",
        "A": "(A) Opportunity to leave lasting accomplishments by recording my in-game achievements as immutable data within the blockchain system",
        "B": "(B) Ability to acquire items through strategic gameplay without relying on a cash shop",
    },
    {
        "Q": "4. What comes to mind when you hear about 'total item ownership'?",
        "A": "(A) Ability to engage in a more open trading system amongst users, fostering a sense of community",
        "B": "(B) Ability to create additional value through freely lending or trading NFT items",
    },
    {
        "Q": "5. Please describe your experience interacting with and using blockchain.",
        "A": "(A) Some experience",
        "B": "(B) Little to no experience",
    },
]

real_answer = [
    {
        "A": "B",
        "B": "A"
    },
    {
        "A": "A",
        "B": "B"
    },
    {
        "A": "B",
        "B": "A"
    },
    {
        "A": "A",
        "B": "B"
    },
    {
        "A": "B",
        "B": "A"
    },
]

view_timeout = 1 * 60


async def get_real_answer(index, select_type):
    return real_answer[index].get(select_type)


class WelcomeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Start", style=ButtonStyle.primary)
    async def button_start(self, _, interaction: Interaction):
        user = interaction.user
        for role in user.roles:
            if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                await interaction.response.send_message(
                    content=f"You have already been granted {role.mention}.",
                    ephemeral=True
                )
                return

        my_selected = {
            "user_id": str(interaction.user.id),
            "A": 0,
            "B": 0,
        }

        content = f"# **{all_question[0].get('Q')}**\n" \
                  f"```" \
                  f"{all_question[0].get('A')}\n\n" \
                  f"{all_question[0].get('B')}" \
                  f"```"

        await interaction.response.send_message(
            content=content,
            view=QuestionSelectView(my_selected, interaction),
            ephemeral=True
        )

    @button(label="Remove Role", style=ButtonStyle.danger)
    async def button_remove_role(self, _, interaction: Interaction):
        user = interaction.user
        for role in user.roles:
            if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                await user.remove_roles(role)
                await interaction.response.send_message(
                    content=f"{role.mention} has been removed.",
                    ephemeral=True
                )
                return

        await interaction.response.send_message(
            content=f"There are no roles to remove.\n"
                    f"Do a Q&A and get a role.",
            ephemeral=True
        )


class QuestionSelectView(View):
    def __init__(self, my_selected, org_interaction: Interaction):
        super().__init__(timeout=view_timeout)
        self.my_selected = my_selected
        self.org_interaction = org_interaction

    @button(label="A", style=ButtonStyle.primary)
    async def button_a(self, _, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        my_real_selected = await get_real_answer(self.my_selected["A"] + self.my_selected["B"], "A")

        if my_real_selected == "A":
            self.my_selected["A"] += 1
        else:
            self.my_selected["B"] += 1

        q_index = self.my_selected["A"] + self.my_selected["B"]

        if q_index > 6:
            user = interaction.user
            for role in user.roles:
                if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                    await self.org_interaction.edit_original_response(
                        content=f"You have already been granted {role.mention}."
                    )
                    return

            await self.add_role(user, interaction)
        else:
            content = f"# **{all_question[q_index].get('Q')}**\n" \
                      f"```" \
                      f"{all_question[q_index].get('A')}\n\n" \
                      f"{all_question[q_index].get('B')}\n" \
                      f"```"
            await self.org_interaction.edit_original_response(
                content=content,
                view=QuestionSelectView(self.my_selected, interaction),
            )

    @button(label="B", style=ButtonStyle.danger)
    async def button_b(self, _, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        my_real_selected = await get_real_answer(self.my_selected["A"] + self.my_selected["B"], "B")

        if my_real_selected == "A":
            self.my_selected["A"] += 1
        else:
            self.my_selected["B"] += 1

        q_index = self.my_selected["A"] + self.my_selected["B"]

        if q_index > 6:
            user = interaction.user
            for role in user.roles:
                if role.id == int(os.getenv("A_ROLE_ID")) or role.id == int(os.getenv("B_ROLE_ID")):
                    await self.org_interaction.edit_original_response(
                        content=f"You have already been granted {role.mention}."
                    )
                    return

            await self.add_role(user, interaction)
        else:
            content = f"# **{all_question[q_index].get('Q')}**\n" \
                      f"```" \
                      f"{all_question[q_index].get('A')}\n\n" \
                      f"{all_question[q_index].get('B')}\n" \
                      f"```"
            await self.org_interaction.edit_original_response(
                content=content,
                view=QuestionSelectView(self.my_selected, interaction),
            )

    async def add_role(self, user, interaction):
        if self.my_selected["A"] > self.my_selected["B"]:
            add_role = interaction.guild.get_role(int(os.getenv("A_ROLE_ID")))
            await user.add_roles(add_role)
            channel_id = "1277481622660321321"
        else:
            add_role = interaction.guild.get_role(int(os.getenv("B_ROLE_ID")))
            await user.add_roles(add_role)
            channel_id = "1277481664175538238"

        await self.org_interaction.edit_original_response(
            view=None,
            content=f"{add_role.mention} is assigned on your test results, and we hope you'll interact with like-minded users in <#{channel_id}>.\n"
                    f"_※ If you want to change your role, click the 'Remove Role' button and you may retake the Tuner's Personality Test._"
        )

    async def on_timeout(self):
        try:
            if self.org_interaction:
                await self.org_interaction.delete_original_response()
        except:
            pass


@bot.command(
    name='open-qna'
)
@commands.has_any_role(*mod_role_ids)
async def open_qna(ctx):
    description = "Choose your preferred answer for each question.\n" \
                  "A role will be assigned based on the test results."

    embed = Embed(title="Tuner's Personality Test", description=description, color=0x9C3EFF)
    view = WelcomeView()
    await ctx.send(embed=embed, view=view)


event_role_ids = list(map(int, os.getenv('EVENT_ROLE_IDS').split(',')))
event_rookie_role_id = int(os.getenv('EVENT_ROOKIE_ROLE_ID'))
event_novice_role_id = int(os.getenv('EVENT_NOVICE_ROLE_ID'))


class RoleClaim(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Claim", style=discord.ButtonStyle.green, custom_id="role_claim")
    async def button_role_claim(self, _, interaction: Interaction):
        own_role_count = 0

        event_rookie_role = interaction.guild.get_role(int(os.getenv("EVENT_ROOKIE_ROLE_ID")))
        event_novice_role = interaction.guild.get_role(int(os.getenv("EVENT_NOVICE_ROLE_ID")))

        user = interaction.user
        user_roles = interaction.user.roles
        for role in user_roles:
            if role.id in event_role_ids:
                own_role_count += 1

        if 3 <= own_role_count < 5:
            add_role = event_rookie_role
            await user.remove_roles(event_novice_role)
            await user.add_roles(add_role)
        elif own_role_count >= 5:
            add_role = event_novice_role
            await user.add_roles(event_rookie_role)
            await user.add_roles(add_role)
        else:
            await user.remove_roles(event_rookie_role)
            await user.remove_roles(event_novice_role)
            await interaction.response.send_message(
                content="You still don't have enough roles.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            content=f"You are given a {add_role.mention}",
            ephemeral=True
        )


@bot.command(
    name='role-claim'
)
@commands.has_any_role(*mod_role_ids)
async def role_claim(ctx):
    description = "Thank you to all the explorers who have been active in the MapleStory Universe community since discord opened!\n\n" \
                  "As a reward for your contribution to energizing the MapleStory Universe community through various activities, you can claim additional roles based on the number of roles you've earned.\n" \
                  "Don't miss out on these upcoming events and be sure to participate to earn your roles.\n\n" \
                  "Depending on how many of the <@&1252111835537215518>, <@&1252112597747105824>, <@&1252112585453469796>, <@&1252112567917350932>, and <@&1252112533981233182> roles you have, you can claim the following roles by pressing the ** 'Claim' ** button.\n\n" \
                  "- [3 roles → <@&1252112617942810697>]\n" \
                  "- [5 roles → <@&1252112640671617074>]\n\n" \
                  "※ If you have 5 or more roles after holding <@&1252112617942810697> role, you can claim the <@&1252112640671617074> role as well."

    embed = Embed(title="Community Special Role", description=description, color=0x9C3EFF)
    view = RoleClaim()
    await ctx.send(embed=embed, view=view)


@bot.event
async def on_ready():
    base_bot.config_logging(logger)
    # bot.add_cog(base_bot.RaffleCog(bot, db))


bot.run(bot_token)
