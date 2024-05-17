import os
from tools.configs import CONFIG_FOLDER, NODE_DATA_PATH

FILEBEAT_TEMPLATE_PATH = os.path.join(CONFIG_FOLDER, 'filebeat.yml.j2')
FILEBEAT_CONFIG_PATH = os.path.join(NODE_DATA_PATH, 'filebeat.yml')

FILEBEAT_CONTAINER_NAME = 'skale_filebeat'

MONITORING_CONTAINERS = os.getenv('MONITORING_CONTAINERS') == 'True'

INFLUX_TOKEN = os.getenv('INFLUX_TOKEN')
INFLUX_URL = os.getenv('INFLUX_URL')

TELEGRAF = os.getenv('TELEGRAF') == 'True'

TELEGRAF_TEMPLATE_PATH = os.path.join(CONFIG_FOLDER, 'telegraf.conf.j2')
TELEGRAF_CONFIG_PATH = os.path.join(CONFIG_FOLDER, 'telegraf.conf')

TELEGRAF_CONTAINER_NAME = 'skale_telegraf'
TELEGRAF_SERVICE_NAME = 'telegraf'
TELEGRAF_IMAGE = 'telegraf:1.27.4'
TELEGRAF_MEM_LIMIT = os.getenv('TELEGRAF_MEM_LIMIT', '1GB')
