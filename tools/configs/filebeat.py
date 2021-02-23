import os
from tools.configs import CONFIG_FOLDER, NODE_DATA_PATH

FILEBEAT_TEMPLATE_PATH = os.path.join(CONFIG_FOLDER, 'filebeat.yml.j2')
FILEBEAT_CONFIG_PATH = os.path.join(NODE_DATA_PATH, 'filebeat.yml')

FILEBEAT_CONTAINER_NAME = 'skale_filebeat'

MONITORING_CONTAINERS = os.getenv('MONITORING_CONTAINERS') == 'True'
