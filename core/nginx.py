import logging

from core.schains.ssl import is_ssl_folder_empty
from tools.configs.nginx import NGINX_TEMPLATE_FILEPATH, NGINX_CONFIG_FILEPATH, NGINX_CONTAINER_NAME
from tools.docker_utils import DockerUtils
from tools.helper import process_template

dutils = DockerUtils()
logger = logging.getLogger(__name__)


def reload_nginx():
    generate_nginx_config()
    restart_nginx_container()


def generate_nginx_config():
    ssl_on = is_ssl_folder_empty()
    template_data = {
        'ssl': ssl_on,
    }
    logger.info(f'Processing nginx template. ssl: {ssl_on}')
    process_template(NGINX_TEMPLATE_FILEPATH, NGINX_CONFIG_FILEPATH, template_data)


def restart_nginx_container():
    nginx_container = dutils.client.containers.get(NGINX_CONTAINER_NAME)
    nginx_container.restart()
