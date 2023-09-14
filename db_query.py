def select_guild_store():
    return """
        select id, guild_id, title, description, image_url
        from stores
        where guild_id = %s
    """


def select_guild_products():
    return """
        select id, name, image, price 
        from products
        where guild_id = %s
    """


def select_guild_user_tickets():
    return """
        select p.id, p.name, p.image, p.price, count(p.id) tickets
        from user_tickets u
        inner join products p on u.product_id = p.id
        where u.guild_id = %s 
        and u.user_id = %s
        group by p.id, p.name, p.image, p.price
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
        select id, name, image, price 
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
        insert into user_tickets(guild_id, user_id, product_id)
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
        insert into products (guild_id, name, image, price)
        values (%s, %s, %s, %s)
    """


def insert_guild_user_point_logs():
    return """
        insert into user_point_logs (guild_id, user_id, point_amount, action_type, action_user_id)
        values (%s, %s, %s, %s, %s)
    """