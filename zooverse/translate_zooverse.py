import os
import sys
import logging
import discord
import deepl
from discord.ui import View, button
from discord.interactions import Interaction
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

bot_token = os.getenv("BOT_TRANSLATE_TOKEN")
guild_id = os.getenv('GUILD_ID')
team_role_ids = list(map(int, os.getenv('TEAM_ROLE_ID').split(',')))
mod_role_ids = list(map(int, os.getenv('MOD_ROLE_ID').split(',')))
deepl_api_key = os.getenv("DEEPL_API_KEY")
allowed_channels = list(map(int, os.getenv('TRANSLATE_CHANNEL_LIST').split(',')))


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f"translate_{folder_name}.log", mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"This is an info message from translate_{folder_name}")


##############################
# Class
##############################
class TranslateButton(View):
    def __init__(self, db, _guild_id, _message_id):
        super().__init__(timeout=None)
        self.db = db
        self.guild_id = _guild_id
        self.message_id = _message_id

    @button(label="Korean", style=discord.ButtonStyle.gray, custom_id="korean_button")
    async def button_kor(self, _, interaction: Interaction):
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                select 
                    message_org,
                    message_kor,
                    message_eng,
                    message_chn
                from messages_translate
                where guild_id = %s
                and message_id = %s
            """, (self.guild_id, self.message_id))

            result = cursor.fetchone()

            if result:
                if result["message_kor"]:
                    answer = result["message_kor"]
                else:
                    translator = deepl.Translator(deepl_api_key)
                    prompt_text: str = result["message_org"]
                    answer = translator.translate_text(prompt_text, target_lang="KO")

                    cursor.execute("""
                        update messages_translate set message_kor = %s
                        where guild_id = %s
                        and message_id = %s
                    """, (answer, self.guild_id, self.message_id))
                    connection.commit()

                description = f"[AI Translation]\n\n{answer}"
                await interaction.response.send_message(
                    content=description,
                    ephemeral=True
                )
        except Exception as e:
            connection.rollback()
            logger.error(f'button_kor db error: {e}')
        finally:
            cursor.close()
            connection.close()

    @button(label="English", style=discord.ButtonStyle.gray, custom_id="english_button")
    async def button_eng(self, _, interaction: Interaction):
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                select 
                    message_org,
                    message_kor,
                    message_eng,
                    message_chn
                from messages_translate
                where guild_id = %s 
                and message_id = %s
            """, (self.guild_id, self.message_id))

            result = cursor.fetchone()

            if result:
                if result["message_eng"]:
                    answer = result["message_eng"]
                else:
                    translator = deepl.Translator(deepl_api_key)
                    prompt_text: str = result["message_org"]
                    answer = translator.translate_text(prompt_text, target_lang="EN-US")

                    cursor.execute("""
                        update messages_translate set message_eng = %s
                        where guild_id = %s 
                        and message_id = %s
                    """, (answer, self.guild_id, self.message_id))
                    connection.commit()

                description = f"[AI Translation]\n\n{answer}"
                await interaction.response.send_message(
                    content=description,
                    ephemeral=True
                )
        except Exception as e:
            connection.rollback()
            logger.error(f'button_eng db error: {e}')
        finally:
            cursor.close()
            connection.close()

    @button(label="Chinese", style=discord.ButtonStyle.gray, custom_id="chinese_button")
    async def button_chn(self, _, interaction: Interaction):
        connection = self.db.get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                select 
                    message_org,
                    message_kor,
                    message_eng,
                    message_chn
                from messages_translate
                where guild_id = %s 
                and message_id = %s
            """, (self.guild_id, self.message_id))

            result = cursor.fetchone()

            if result:
                if result["message_chn"]:
                    answer = result["message_chn"]
                else:
                    translator = deepl.Translator(deepl_api_key)
                    prompt_text: str = result["message_org"]
                    answer = translator.translate_text(prompt_text, target_lang="ZH")

                    cursor.execute("""
                        update messages_translate set message_chn = %s
                        where guild_id = %s 
                        and message_id = %s
                    """, (answer, self.guild_id, self.message_id))
                    connection.commit()

                description = f"[AI Translation]\n\n{answer}"
                await interaction.response.send_message(
                    content=description,
                    ephemeral=True
                )
        except Exception as e:
            connection.rollback()
            logger.error(f'button_chn db error: {e}')
        finally:
            cursor.close()
            connection.close()


@bot.event
async def on_message(message):
    # 자신의 봇 메시지만 무시
    if message.author == bot.user:
        return

    # 허용된 채널에서 메시지가 있고, 내용이 있는 경우에만 처리
    if message.channel.id in allowed_channels and len(message.content.strip()) > 0:
        await handle_translation(message)


async def handle_translation(message):
    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                select id
                from messages_translate
                where guild_id = %s 
                and message_id = %s
            """, (guild_id, message.id))
            result = cursor.fetchone()

            if not result:
                cursor.execute("""
                    insert into messages_translate(guild_id, message_id, channel_name, user_id, user_name, message_org)
                    values (%s, %s, %s, %s, %s, %s) 
                """, (guild_id, message.id, message.channel.name, message.author.id, message.author, message.content))
                connection.commit()

            view = TranslateButton(db, guild_id, message.id)
            # custom_id를 각 버튼에 추가하여 영구적으로 만들기
            for child in view.children:
                if isinstance(child, discord.ui.Button):
                    child.custom_id = f"{child.label.lower()}_{message.id}"
            await message.channel.send(view=view, reference=message)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        connection.rollback()
    finally:
        connection.close()


@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')

    connection = db.get_connection()
    try:
        with connection.cursor() as cursor:
            # timestamp 컬럼을 사용하여 최근 30일 내의 메시지만 가져오기
            cursor.execute("""
                SELECT message_id 
                FROM messages_translate 
                WHERE guild_id = %s 
                and timestamp > DATE_SUB(NOW(), INTERVAL 30 DAY)
            """, guild_id)
            messages = cursor.fetchall()

            # 각 메시지에 대한 View 등록
            for message in messages:
                message_id = message['message_id']
                view = TranslateButton(db, guild_id, message_id)
                # 각 버튼에 custom_id 설정
                for child in view.children:
                    if isinstance(child, discord.ui.Button):
                        child.custom_id = f"{child.label.lower()}_{message_id}"
                bot.add_view(view)

            logger.info(f"Registered {len(messages)} persistent views for translation buttons")
    except Exception as e:
        logger.error(f"Error registering persistent views: {e}")
    finally:
        connection.close()


bot.run(bot_token)
