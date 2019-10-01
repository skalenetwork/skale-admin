import os
from tools.configs import NODE_DATA_PATH

LOG_FOLDER_NAME = 'log'
LOG_FOLDER = os.path.join(NODE_DATA_PATH, LOG_FOLDER_NAME)

ADMIN_LOG_FILENAME = 'admin.log'
ADMIN_LOG_PATH = os.path.join(LOG_FOLDER, ADMIN_LOG_FILENAME)

DEBUG_LOG_FILENAME = 'debug.log'
DEBUG_LOG_PATH = os.path.join(LOG_FOLDER, DEBUG_LOG_FILENAME)

LOG_FILE_SIZE_MB = 100
LOG_FILE_SIZE_BYTES = LOG_FILE_SIZE_MB * 1000000

LOG_BACKUP_COUNT = 3

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
