import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB


class Database:
    def __init__(self, host, port, user, password, db):
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=5,
            mincached=2,
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=db,
            charset='utf8mb4',
            cursorclass=DictCursor
        )

    def get_connection(self):
        return self.pool.connection()