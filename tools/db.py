import redis

from peewee import SqliteDatabase

from tools.configs.db import DB_FILE, DB_PRAGMAS, REDIS_URI

db = SqliteDatabase(DB_FILE, DB_PRAGMAS)


def get_database():
    return db


cpool: redis.ConnectionPool = redis.ConnectionPool.from_url(REDIS_URI)
rs: redis.Redis = redis.Redis(connection_pool=cpool)
