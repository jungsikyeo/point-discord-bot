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
                 where r.guild_id = t_max_round.guild_id
                 and r.round_status = 'OPEN') round_status
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
        select p.id, r.round, p.item_type, p.name, p.image, p.price, p.quantity
        from products p 
        inner join rounds r on r.guild_id = p.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where p.guild_id = %s
    """


def select_guild_products_raffle():
    return """
        select p.id, r.round, p.item_type, p.name, p.image, p.price, p.quantity
        from products p 
        inner join rounds r on r.guild_id = p.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where p.guild_id = %s
        AND p.item_type = 'RAFFLE'
    """


def select_guild_user_tickets():
    return """
        select p.id, p.round, p.item_type, p.name, p.image, p.price, p.quantity, count(p.id) tickets
        from user_tickets u
        inner join products p on p.guild_id = u.guild_id and p.id = u.product_id
        inner join rounds r on r.guild_id = u.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where u.guild_id = %s 
        and u.user_id = %s
        group by p.id, p.item_type, p.name, p.image, p.price
    """


def select_guild_raffle_user_tickets():
    return """
        select u.user_id, p.name, count(u.id) tickets
        from user_tickets u
        inner join products p on p.guild_id = u.guild_id and p.id = u.product_id
        inner join rounds r on r.guild_id = u.guild_id and r.round = p.round and r.round_status = 'OPEN'
        where u.guild_id = %s
        and p.item_type = 'RAFFLE'
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
        select p.id, p.item_type, p.name, p.image, p.price, p.quantity, count(ut.user_id) buy_count
        from products p
        left outer join user_tickets ut on p.id = ut.product_id
        where p.guild_id = %s
          and p.id = %s
        group by p.id, p.item_type, p.name, p.image, p.price, p.quantity
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
        and round = %s
        and name = %s
    """


def insert_guild_product():
    return """
        insert into products (guild_id, round, item_type, name, image, price, quantity)
        values (%s, %s, %s, %s, %s, %s, %s)
    """


def insert_guild_user_point_logs():
    return """
        insert into user_point_logs (
            guild_id, user_id, point_amount, 
            before_point, after_point, action_type, action_user_id,
            channel_id, channel_name
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def select_today_self_rewards():
    return """
        select max(timestamp) last_self_rewards
        from user_point_logs
        where guild_id = %s
        and user_id = %s
        and action_type = %s
    """


def insert_guild_user_roles_reset():
    return """
        insert into user_roles_reset (guild_id, action_user_id)
        values (%s, %s)
    """


def update_guild_user_roles_reset():
    return """
        update user_roles_reset set
             reset_end_time = current_timestamp,
             action_user_id = %s,
             reset_user_count = %s
        where id = %s
    """


def select_last_reset_end_time():
    return """
        select reset_end_time
        from user_roles_reset
        where guild_id = %s 
        and reset_end_time is not null
        order by id desc
        limit 1
    """


def select_guild_user_claim_role():
    return """
        select guild_id, user_id, role_name, timestamp
        from user_roles_claim
        where guild_id = %s
        and user_id = %s
        and role_name = %s
        and timestamp > %s
    """


def insert_guild_user_claim_role():
    return """
        insert into user_roles_claim (guild_id, user_id, role_name)
        values (%s, %s, %s)
    """


def select_guild_user_roles_claim_point():
    return """
        select guild_id, role_name, point
        from user_roles_claim_point
        where guild_id = %s
    """

