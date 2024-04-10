import redis
import statsd

from peewee import SqliteDatabase

from tools.configs.db import DB_FILE, DB_PRAGMAS, REDIS_URI
from tools.configs import STATSD_HOST, STATSD_PORT

db = SqliteDatabase(DB_FILE, DB_PRAGMAS)
cpool: redis.ConnectionPool = redis.ConnectionPool.from_url(REDIS_URI)
rs: redis.Redis = redis.Redis(connection_pool=cpool)
stcd = statsd.StatsClient(STATSD_HOST, STATSD_PORT)


def get_database():
    return db


def get_statsd_client():
    return stcd
