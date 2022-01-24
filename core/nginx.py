import logging

from core.schains.ssl import is_ssl_folder_empty
from tools.configs.nginx import (
    NGINX_TEMPLATE_FILEPATH,
    NGINX_CONFIG_FILEPATH,
    NGINX_CONTAINER_NAME
)
from tools.docker_utils import DockerUtils
from tools.helper import process_template

gdutils = DockerUtils()
logger = logging.getLogger(__name__)


def reload_nginx(
    template_filepath=NGINX_TEMPLATE_FILEPATH,
    config_filepath=NGINX_CONFIG_FILEPATH,
    dutils=None
):
    dutils = dutils or gdutils
    generate_nginx_config(
        template_filepath=template_filepath,
        config_filepath=config_filepath
    )
    restart_nginx_container(dutils=dutils)


def generate_nginx_config(
    template_filepath=NGINX_TEMPLATE_FILEPATH,
    config_filepath=NGINX_CONFIG_FILEPATH

):
    ssl_on = not is_ssl_folder_empty()
    template_data = {
        'ssl': ssl_on,
    }
    logger.info(f'Processing nginx template. ssl: {ssl_on}')
    process_template(template_filepath, config_filepath, template_data)


def restart_nginx_container(dutils=None):
    dutils = dutils or gdutils
    nginx_container = dutils.client.containers.get(NGINX_CONTAINER_NAME)
    nginx_container.restart()
