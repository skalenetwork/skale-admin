import os
from tools.configs import CONFIG_FOLDER
from tools.helper import read_json

DATA_DIR_CONTAINER_PATH = '/data_dir'

SCHAIN_CONTAINER = 'schain'
IMA_CONTAINER = 'ima'

CONTAINER_NAME_PREFIX = 'skale'
CONTAINERS_FILENAME = 'containers.json'

CONTAINERS_FILEPATH = os.path.join(CONFIG_FOLDER, CONTAINERS_FILENAME)
CONTAINERS_INFO = read_json(CONTAINERS_FILEPATH)

CONTAINER_NOT_FOUND = 'not_found'
EXITED_STATUS = 'exited'
RUNNING_STATUS = 'running'