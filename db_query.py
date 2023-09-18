def select_guild_store():
    return """
        select id, guild_id, title, description, image_url,
               raffle_announce_channel, raffle_bot_user_id, raffle_time_hour, raffle_time_minute, auto_raffle_status
        from stores
        where guild_id = %s
    """


def update_guild_store_raffle():
    return """
        update stores set auto_raffle_status = %s
        where guild_id = %s
    """


def select_guild_store_round():
    return """
        with t_max_round as (
            select guild_id, max(round) max_round
            from rounds
            where guild_id = %s
            group by guild_id
        ),
        t_status_round as (
            select guild_id, max_round,
                (select IF(count(r.round) > 0, 'OPEN', 'CLOSE') round_status
                 from rounds r
                 where r.round_status = 'OPEN') round_status
            from t_max_round
        )
        select t.guild_id, s.title, s.description, s.image_url, t.max_round, t.round_status
        from t_status_round t
        inner join stores s on t.guild_id = s.guild_id
    """


def insert_guild_store_round():
    return """
        insert into rounds (guild_id, round, round_status)
        values (%s, %s, %s)
    """


def insert_guild_store():
    return """
        insert into stores (guild_id, title, description, image_url)
        values (%s, %s, %s, %s)
    """


def update_guild_store():
    return """
        update stores 
        set title = %s,
            description = %s,
            image_url = %s
        where guild_id = %s
    """


def select_guild_products():
    return """
        select p.id, r.round, p.name, p.image, p.price, p.quantity
        from products p 
        inner join rounds r on r.guild_id = p.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where p.guild_id = %s
    """


def select_guild_user_tickets():
    return """
        select p.id, p.round, p.name, p.image, p.price, p.quantity, count(p.id) tickets
        from user_tickets u
        inner join products p on p.guild_id = u.guild_id and p.id = u.product_id
        inner join rounds r on r.guild_id = u.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where u.guild_id = %s 
        and u.user_id = %s
        group by p.id, p.name, p.image, p.price
    """


def select_guild_raffle_user_tickets():
    return """
        select u.user_id, p.name, count(u.id) tickets
        from user_tickets u
        inner join products p on p.guild_id = u.guild_id and p.id = u.product_id
        inner join rounds r on r.guild_id = u.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where u.guild_id = %s
        group by u.user_id, p.id, p.name 
    """


def select_guild_user_points():
    return """
        select points
        from user_points
        where guild_id = %s 
        and user_id = %s
    """


def select_guild_product():
    return """
        select id, name, image, price, quantity
        from products
        where guild_id = %s 
        and id = %s
    """


def select_guild_user_point():
    return """
        select points
        from user_points
        where guild_id = %s 
        and user_id = %s
    """


def insert_guild_user_ticket():
    return """
        insert into user_tickets(user_id, product_id, guild_id)
        values (%s, %s, %s)
    """


def insert_guild_user_point():
    return """
        insert into user_points (guild_id, user_id, points)
        values (%s, %s, %s)
    """


def update_guild_user_point():
    return """
        update user_points set points = %s
        where guild_id = %s
        and user_id = %s
    """


def select_guild_product_count():
    return """
        select count(id) cnt
        from products
        where guild_id = %s 
        and name = %s
    """


def insert_guild_product():
    return """
        insert into products (guild_id, round, name, image, price, quantity)
        values (%s, %s, %s, %s, %s, %s)
    """


def insert_guild_user_point_logs():
    return """
        insert into user_point_logs (guild_id, user_id, point_amount, action_type, action_user_id)
        values (%s, %s, %s, %s, %s)
    """


def insert_guild_round_winners():
    return """
        insert into round_winners (product_id, guild_id, round, user_id, action_type, action_user_id)
        values (%s, %s, %s, %s, %s, %s)
    """


def update_guild_rounds():
    return """
        update rounds set round_status = %s
        where guild_id = %s
        and round = %s
    """