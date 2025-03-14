import random
import os
import db_query as query
from prettyprinter import pprint
from dotenv import load_dotenv


global logger


def config_logging(module_logger):
    global logger
    logger = module_logger


load_dotenv()
mysql_ip = os.getenv("MYSQL_IP")
mysql_port = os.getenv("MYSQL_PORT")
mysql_id = os.getenv("MYSQL_ID")
mysql_passwd = os.getenv("MYSQL_PASSWD")
mysql_db = os.getenv("MYSQL_DB")


def pick_winner(weights):
    total = sum(weights.values())
    rand_val = random.randint(1, total)
    current = 0

    for user, weight in weights.items():
        current += weight
        if rand_val <= current:
            return user


def get_products(db, guild_id, item_type):
    connection = db.get_connection()
    cursor = connection.cursor()
    products = None
    try:
        cursor.execute(
            query.select_guild_products_raffle(),
            (guild_id, item_type)
        )
        products = cursor.fetchall()
    except Exception as e:
        logger.error(f'get_products db error: {e}')
    finally:
        cursor.close()
        connection.close()

    return products


def get_user_tickets(db, guild_id, item_type):
    connection = db.get_connection()
    cursor = connection.cursor()
    ticket_holders = {}
    try:
        cursor.execute(
            query.select_guild_raffle_user_tickets(),
            (guild_id, item_type)
        )
        user_tickets = cursor.fetchall()

        for ticket in user_tickets:
            user_id = ticket.get('user_id')
            name = ticket.get('name')
            tickets = ticket.get('tickets')

            if user_id not in ticket_holders:
                ticket_holders[user_id] = {}

            ticket_holders[user_id][name] = tickets
    except Exception as e:
        logger.error(f'get_user_tickets db error: {e}')
    finally:
        cursor.close()
        connection.close()

    return ticket_holders


def setting_data(db, guild_id, item_type):
    products = get_products(db, guild_id, item_type)
    prizes = {product.get('name'): product.get('quantity') for product in products}
    ticket_holders = get_user_tickets(db, guild_id, item_type)

    return products, prizes, ticket_holders


def start_raffle(db, guild_id, action_type, action_user_id):
    connection = db.get_connection()
    cursor = connection.cursor()
    products, prizes, ticket_holders = setting_data(db, guild_id, 'RAFFLE')
    winners = {}
    try:
        for prize, count in prizes.items():
            already_won = set()
            weights = {user: tickets.get(prize, 0) for user, tickets in ticket_holders.items()}

            for _ in range(count):
                weights = {user: weight for user, weight in weights.items() if user not in already_won}

                if sum(weights.values()) == 0:
                    print(f"No tickets for {prize}. Skipping...")
                    continue

                winner = pick_winner(weights)
                winners.setdefault(prize, []).append(winner)
                already_won.add(winner)
        pprint(winners)
        raffle_round = 0
        for product in products:
            for winner in winners[product.get('name')]:
                product_id = product.get('id')
                raffle_round = product.get('round')
                cursor.execute(
                    query.insert_guild_round_winners(),
                    (product_id, guild_id, raffle_round, winner, action_type, action_user_id,)
                )
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f'start_raffle db error: {e}')
    finally:
        cursor.close()
        connection.close()
    return winners


def start_fcfs(db, guild_id, action_type, action_user_id):
    connection = db.get_connection()
    cursor = connection.cursor()
    products, prizes, ticket_holders = setting_data(db, guild_id, 'FCFS')
    winners = {}
    try:
        for prize, count in prizes.items():
            weights = {user: tickets.get(prize, 0) for user, tickets in ticket_holders.items()}
            for user, weight in weights.items():
                winners.setdefault(prize, []).append(user)
        pprint(winners)
        raffle_round = 0
        for product in products:
            for winner in winners[product.get('name')]:
                product_id = product.get('id')
                raffle_round = product.get('round')
                cursor.execute(
                    query.insert_guild_round_winners(),
                    (product_id, guild_id, raffle_round, winner, action_type, action_user_id,)
                )
        cursor.execute(
            query.update_guild_rounds(),
            ('CLOSE', guild_id, raffle_round)
        )
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f'start_fcfs db error: {e}')
    finally:
        cursor.close()
        connection.close()
    return winners

# if __name__ == '__main__':
#     if len(sys.argv) > 1:
#         start_raffle(sys.argv[1], 'BOT-AUTO', sys.argv[2])
#     else:
#         print("No argument provided")
