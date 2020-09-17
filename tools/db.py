from peewee import SqliteDatabase

from tools.configs.db import DB_FILE, DB_PRAGMAS

db = SqliteDatabase(DB_FILE, DB_PRAGMAS)


def get_database():
    return db
