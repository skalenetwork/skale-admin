import os
from tools.configs import NODE_DATA_PATH

# mysql db

MYSQL_DB_USER = os.environ["DB_USER"]
MYSQL_DB_PASSWORD = os.environ["DB_PASSWORD"]
MYSQL_DB_NAME = 'db_skale'
MYSQL_DB_HOST = '127.0.0.1'
MYSQL_DB_PORT = int(os.environ["DB_PORT"])

# sqlite db

DB_FILENAME = 'skale.db'
DB_FILE = os.path.join(NODE_DATA_PATH, DB_FILENAME)
