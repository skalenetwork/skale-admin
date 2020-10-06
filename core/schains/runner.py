#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
import copy
from docker.types import LogConfig, Ulimit

from core.schains.volume import get_container_limits, get_schain_volume_config
from core.schains.config.helper import (
    get_schain_container_cmd,
    get_schain_env,
    get_skaled_http_address
)
from core.schains.ima import get_ima_env
from core.schains.helper import send_rotation_request, get_schain_dir_path_host
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from tools.configs.containers import (CONTAINERS_INFO, CONTAINER_NAME_PREFIX, SCHAIN_CONTAINER,
                                      IMA_CONTAINER, DATA_DIR_CONTAINER_PATH)
from tools.configs import (NODE_DATA_PATH_HOST, SCHAIN_NODE_DATA_PATH, SKALE_DIR_HOST,
                           SKALE_VOLUME_PATH, SCHAIN_DATA_PATH)

docker_utils = DockerUtils()
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


def run_container(type, schain_name, env, cmd=None, volume_config=None,
                  cpu_shares_limit=None, mem_limit=None,
                  dutils=None, volume_mode=None):
    if not dutils:
        dutils = docker_utils
    image_name, container_name, run_args, custom_args = get_container_info(type, schain_name)

    add_config_volume(run_args, schain_name, mode=volume_mode)

    if custom_args.get('logs', None):
        run_args['log_config'] = get_logs_config(custom_args['logs'])
    if custom_args.get('ulimits_list', None):
        run_args['ulimits'] = get_ulimits_config(custom_args['ulimits_list'])
    if volume_config:
        run_args['volumes'].update(volume_config)
    if cpu_shares_limit:
        run_args['cpu_shares'] = cpu_shares_limit
    if mem_limit:
        run_args['mem_limit'] = mem_limit
    run_args['environment'] = env
    if cmd:
        run_args['command'] = cmd

    logger.info(arguments_list_string({'Container name': container_name, 'Image name': image_name,
                                       'Args': run_args}, 'Running container...'))
    cont = dutils.run_container(image_name, container_name, **run_args)
    logger.info(arguments_list_string({'Container name': container_name, 'Container id': cont.id},
                                      'Container created', 'success'))
    return cont


def restart_container(type, schain):
    schain_name = schain['name']
    container_name = get_container_name(type, schain_name)

    logger.info(arguments_list_string({'Container name': container_name},
                                      'Restarting container...'))
    cont = docker_utils.restart(container_name)
    return cont


def run_schain_container(schain, public_key=None, start_ts=None, dutils=None,
                         volume_mode=None, ulimit_check=True, enable_ssl=True):
    schain_name = schain['name']
    cpu_shares_limit, mem_limit = get_container_limits(schain)
    volume_config = get_schain_volume_config(
        schain_name,
        DATA_DIR_CONTAINER_PATH,
        mode=volume_mode
    )
    env = get_schain_env(ulimit_check=ulimit_check)
    cmd = get_schain_container_cmd(
        schain_name,
        public_key,
        start_ts,
        enable_ssl=enable_ssl
    )
    run_container(SCHAIN_CONTAINER, schain_name, env, cmd,
                  volume_config, cpu_shares_limit,
                  mem_limit, dutils=dutils, volume_mode=volume_mode)


def set_rotation_for_schain(schain_name: str, timestamp: int) -> None:
    endpoint = get_skaled_http_address(schain_name)
    url = f'http://{endpoint.ip}:{endpoint.port}'
    send_rotation_request(url, timestamp)


def run_ima_container(schain_name: str, dutils: DockerUtils = None) -> None:
    dutils = dutils or docker_utils
    env = get_ima_env(schain_name)
    run_container(IMA_CONTAINER, schain_name, env, dutils=dutils)


def add_config_volume(run_args, schain_name, mode=None):
    if not run_args.get('volumes', None):
        run_args['volumes'] = {}
    schain_data_dir_path = get_schain_dir_path_host(schain_name)

    # mount /skale_node_data
    run_args['volumes'][NODE_DATA_PATH_HOST] = {
        'bind': SCHAIN_NODE_DATA_PATH,
        'mode': mode or 'ro'
    }
    # mount /skale_vol
    run_args['volumes'][SKALE_DIR_HOST] = {
        'bind': SKALE_VOLUME_PATH,
        'mode': mode or 'ro'
    }
    # mount /skale_schain_data
    run_args['volumes'][schain_data_dir_path] = {
        'bind': SCHAIN_DATA_PATH,
        'mode': mode or 'rw'
    }


def is_exited_with_zero(schain_name, dutils=None):
    dutils = dutils or docker_utils
    info = get_schain_container_info(schain_name, dutils)
    return dutils.is_container_exited_with_zero(info)


def is_exited(schain_name, dutils=None):
    if not dutils:
        dutils = docker_utils
    info = get_schain_container_info(schain_name, dutils)
    return dutils.is_container_exited(info)


def get_schain_container_info(schain_name, dutils):
    name = get_container_name(SCHAIN_CONTAINER, schain_name)
    return dutils.get_info(name)
