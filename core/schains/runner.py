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

import copy
import logging

from docker.types import LogConfig, Ulimit

from core.schains.volume import get_schain_volume_config
from core.schains.limits import get_schain_limit, get_ima_limit, get_schain_type
from core.schains.types import MetricType, ContainerType
from core.schains.skaled_exit_codes import SkaledExitCodes
from core.schains.cmd import get_schain_container_cmd
from core.schains.config.helper import get_schain_env
from core.schains.ima import get_ima_env
from core.schains.config.directory import schain_config_dir_host
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from tools.configs.containers import (
    CONTAINERS_INFO,
    CONTAINER_NAME_PREFIX,
    DATA_DIR_CONTAINER_PATH,
    IMA_CONTAINER,
    SCHAIN_CONTAINER,
    SCHAIN_STOP_TIMEOUT
)
from tools.configs import (NODE_DATA_PATH_HOST, SCHAIN_NODE_DATA_PATH, SKALE_DIR_HOST,
                           SKALE_VOLUME_PATH, SCHAIN_CONFIG_DIR_SKALED)

logger = logging.getLogger(__name__)


def is_container_exists(
    schain_name,
    container_type=SCHAIN_CONTAINER,
    dutils=None
):
    dutils = dutils or DockerUtils()
    container_name = get_container_name(container_type, schain_name)
    return dutils.is_container_exists(container_name)


def get_container_image(
    schain_name,
    container_type=SCHAIN_CONTAINER,
    dutils=None
):
    dutils = dutils or DockerUtils()
    container_name = get_container_name(container_type, schain_name)
    return dutils.get_container_image_name(container_name)


def is_container_running(
    schain_name,
    container_type=SCHAIN_CONTAINER,
    dutils=None
):
    dutils = dutils or DockerUtils()
    container_name = get_container_name(container_type, schain_name)
    return dutils.is_container_running(container_name)


def get_image_name(type: str, new: bool = False) -> str:
    tag_field = 'version'
    if type == IMA_CONTAINER and new:
        tag_field = 'new_version'
    container_info = CONTAINERS_INFO[type]
    image_base_name = container_info['name']
    tag = container_info[tag_field]
    return f'{image_base_name}:{tag}'


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


def run_container(
    type,
    schain_name,
    env,
    cmd=None,
    volume_config=None,
    cpu_shares_limit=None,
    mem_limit=None,
    image=None,
    dutils=None,
    volume_mode=None
):
    dutils = dutils or DockerUtils()
    default_image, container_name, run_args, custom_args = get_container_info(
        type, schain_name)

    image_name = image or default_image

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


def restart_container(
    type,
    schain,
    timeout=SCHAIN_STOP_TIMEOUT,
    dutils=None
):
    dutils = dutils or DockerUtils()
    schain_name = schain['name']
    container_name = get_container_name(type, schain_name)

    logger.info(arguments_list_string({'Container name': container_name},
                                      'Restarting container...'))
    cont = dutils.restart(container_name, timeout=SCHAIN_STOP_TIMEOUT)
    return cont


def run_schain_container(
    schain,
    download_snapshot=False,
    start_ts=None,
    dutils=None,
    volume_mode=None,
    ulimit_check=True,
    snapshot_from: str = '',
    enable_ssl=True
):
    schain_name = schain['name']
    schain_type = get_schain_type(schain['partOfNode'])
    cpu_limit = get_schain_limit(schain_type, MetricType.cpu_shares)
    mem_limit = get_schain_limit(schain_type, MetricType.mem)

    volume_config = get_schain_volume_config(
        schain_name,
        DATA_DIR_CONTAINER_PATH,
        mode=volume_mode
    )
    env = get_schain_env(ulimit_check=ulimit_check)

    cmd = get_schain_container_cmd(
        schain_name,
        start_ts,
        download_snapshot=download_snapshot,
        enable_ssl=enable_ssl,
        snapshot_from=snapshot_from
    )
    run_container(SCHAIN_CONTAINER, schain_name, env, cmd,
                  volume_config, cpu_limit,
                  mem_limit, dutils=dutils, volume_mode=volume_mode)


def run_ima_container(
    schain: dict,
    mainnet_chain_id: int,
    image: str,
    dutils: DockerUtils = None
) -> None:
    dutils = dutils or DockerUtils()
    env = get_ima_env(schain['name'], mainnet_chain_id)

    schain_type = get_schain_type(schain['partOfNode'])
    cpu_limit = get_ima_limit(schain_type, MetricType.cpu_shares)
    mem_limit = get_ima_limit(schain_type, MetricType.mem)

    run_container(
        type=IMA_CONTAINER,
        schain_name=schain['name'],
        env=env.to_dict(),
        cpu_shares_limit=cpu_limit,
        mem_limit=mem_limit,
        image=image,
        dutils=dutils
    )


def add_config_volume(run_args, schain_name, mode=None):
    if not run_args.get('volumes', None):
        run_args['volumes'] = {}
    config_dir_host = schain_config_dir_host(schain_name)

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
    run_args['volumes'][config_dir_host] = {
        'bind': SCHAIN_CONFIG_DIR_SKALED,
        'mode': mode or 'rw'
    }


def is_exited(
    schain_name: str,
    container_type: ContainerType = ContainerType.schain,
    dutils: DockerUtils = None
):
    dutils = dutils or DockerUtils()
    name = get_container_name(container_type.name, schain_name)
    return dutils.is_container_exited(name)


def is_schain_container_failed(
    schain_name: str,
    dutils: DockerUtils = None
) -> bool:
    dutils = dutils or DockerUtils()
    name = get_container_name(SCHAIN_CONTAINER, schain_name)
    created = dutils.is_container_created(name)
    exited = dutils.is_container_exited(name)
    exit_code = dutils.container_exit_code(name)
    bad_state = created or exited and exit_code != SkaledExitCodes.EC_SUCCESS
    if bad_state:
        logger.warning(f'{name} is in bad state - exited: {exited}, created: {created}')
    return bad_state


def is_new_image_pulled(type: str, dutils: DockerUtils) -> bool:
    image = get_image_name(type, new=True)
    return dutils.pulled(image)


def remove_container(schain_name: str, type: str, dutils: DockerUtils):
    container = get_container_name(type=type, schain_name=schain_name)
    dutils.safe_rm(container)


def pull_new_image(type: str, dutils: DockerUtils) -> None:
    image = get_image_name(type, new=True)
    if not dutils.pulled(image):
        logger.info('Pulling new image %s', image)
        dutils.pull(image)
