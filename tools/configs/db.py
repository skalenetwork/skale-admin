import os

# mysql db

MYSQL_DB_USER = os.environ["DB_USER"]
MYSQL_DB_PASSWORD = os.environ["DB_PASSWORD"]
MYSQL_DB_NAME = 'db_skale'
MYSQL_DB_HOST = '127.0.0.1'
MYSQL_DB_PORT = int(os.environ["DB_PORT"])
