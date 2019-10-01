import logging
import copy
from docker.types import LogConfig, Ulimit

from core.schains.volume import get_container_limits, get_schain_volume_config
from tools.docker_utils import DockerUtils
from tools.str_formatters import argumets_list_string
from tools.configs.containers import (CONTAINERS_INFO, CONTAINER_NAME_PREFIX, SCHAIN_CONTAINER,
                                      IMA_CONTAINER, DATA_DIR_CONTAINER_PATH)

dutils = DockerUtils()
logger = logging.getLogger(__name__)


def get_image_name(type):
    container_info = CONTAINERS_INFO[type]
    return f'{container_info["name"]}:{container_info["version"]}'


def get_container_name(type, schain_name):
    return f"{CONTAINER_NAME_PREFIX}_{type}_{schain_name}"


def get_container_args(type):
    return copy.deepcopy(CONTAINERS_INFO[type]['args'])


def get_container_custom_args(type):
    return copy.deepcopy(CONTAINERS_INFO[type]['custom_args'])


def get_container_info(type, schain_name):
    return (get_image_name(type), get_container_name(type, schain_name),
            get_container_args(type), get_container_custom_args(type))


def get_logs_config(config):
    return LogConfig(type=LogConfig.types.JSON, config=config)


def get_ulimits_config(config):
    return list(map(lambda ulimit:
                    Ulimit(name=ulimit['name'], soft=ulimit['soft'], hard=ulimit['hard']), config))


def run_container(type, schain, env, volume_config=None, cpu_limit=None, mem_limit=None):
    schain_name = schain['name']
    image_name, container_name, run_args, custom_args = get_container_info(type, schain_name)

    if custom_args.get('logs', None):
        run_args['log_config'] = get_logs_config(custom_args['logs'])
    if custom_args.get('ulimits_list', None):
        run_args['ulimits'] = get_ulimits_config(custom_args['ulimits_list'])
    if volume_config:
        run_args['volumes'].update(volume_config)
    if cpu_limit:
        run_args['nano_cpus'] = cpu_limit
    if mem_limit:
        run_args['mem_limit'] = mem_limit
    run_args['environment'] = env

    logger.info(argumets_list_string({'Container name': container_name, 'Image name': image_name,
                                      'Args': run_args}, 'Running container...'))
    cont = dutils.client.containers.run(image_name, name=container_name, detach=True, **run_args)
    logger.info(argumets_list_string({'Container name': container_name, 'Container id': cont.id},
                                     'Container created', 'success'))
    return cont


def run_schain_container(schain, env):
    cpu_limit, mem_limit = get_container_limits(schain)
    volume_config = get_schain_volume_config(schain['name'], DATA_DIR_CONTAINER_PATH)
    run_container(SCHAIN_CONTAINER, schain, env, volume_config, cpu_limit, mem_limit)


def run_ima_container(schain, env):
    run_container(IMA_CONTAINER, schain, env)
