import os

from tools.configs import CONFIG_FOLDER, NODE_DATA_PATH

NGINX_CONTAINER_NAME = 'skale_nginx'
NGINX_TEMPLATE_FILEPATH = os.path.join(CONFIG_FOLDER, 'nginx.conf.j2')
NGINX_CONFIG_FILEPATH = os.path.join(NODE_DATA_PATH, 'nginx.conf')
