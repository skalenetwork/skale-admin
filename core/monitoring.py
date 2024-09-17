#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2020 SKALE Labs
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
from typing import Optional

from tools.helper import process_template
from tools.docker_utils import DockerUtils, get_docker_group_id

from tools.configs import SKALE_DIR_HOST
from tools.configs.monitoring import (
    FILEBEAT_TEMPLATE_PATH, FILEBEAT_CONTAINER_NAME,
    FILEBEAT_CONFIG_PATH,
    INFLUX_URL,
    TELEGRAF,
    TELEGRAF_CONTAINER_NAME, TELEGRAF_IMAGE,
    TELEGRAF_TEMPLATE_PATH,
    TELEGRAF_CONFIG_PATH,
    TELEGRAF_MEM_LIMIT
)

logger = logging.getLogger(__name__)


class TelegrafNotConfiguredError(Exception):
    pass


def update_filebeat_service(node_ip, node_id, skale, dutils: Optional[DockerUtils] = None):
    dutils = dutils or DockerUtils()
    contract_address = skale.manager.address
    template_data = {
        'ip': node_ip,
        'id': node_id,
        'contract_address': contract_address
    }

    logger.info('Configuring filebeat %s', template_data)
    process_template(FILEBEAT_TEMPLATE_PATH, FILEBEAT_CONFIG_PATH, template_data)
    filebeat_container = dutils.client.containers.get(FILEBEAT_CONTAINER_NAME)
    filebeat_container.restart()
    logger.info('Filebeat config updated, telegraf restarted')


def filebeat_config_processed() -> bool:
    with open(FILEBEAT_CONFIG_PATH) as f:
        return 'id: ' in f.read()


def ensure_telegraf_running(dutils: Optional[DockerUtils] = None) -> None:
    dutils = dutils or DockerUtils()
    if dutils.is_container_exists(TELEGRAF_CONTAINER_NAME):
        dutils.restart(TELEGRAF_CONTAINER_NAME)
    else:
        group_id = get_docker_group_id()
        dutils.run_container(
            image_name=TELEGRAF_IMAGE,
            name=TELEGRAF_CONTAINER_NAME,
            network_mode='host',
            user=f'telegraf:{group_id}',
            restart_policy={'name': 'on-failure'},
            environment={'HOST_PROC': '/host/proc'},
            volumes={
                '/proc': {'bind': '/host/proc', 'mode': 'ro'},
                f'{SKALE_DIR_HOST}/config/telegraf.conf': {'bind': '/etc/telegraf/telegraf.conf', 'mode': 'ro'},  # noqa
                f'{SKALE_DIR_HOST}/node_data/telegraf': {'bind': '/var/lib/telegraf', 'mode': 'rw'},
                '/var/run/skale/': {'bind': '/var/run/skale', 'mode': 'rw'}
            },
            mem_limit=TELEGRAF_MEM_LIMIT
        )


def update_telegraf_service(
    node_ip: str,
    node_id: int,
    url: str = INFLUX_URL,
    dutils: Optional[DockerUtils] = None
) -> None:
    dutils = dutils or DockerUtils()
    template_data = {
        'ip': node_ip,
        'node_id': str(node_id),
        'url': url
    }
    missing = list(filter(lambda k: not template_data[k], template_data))

    if missing:
        emsg = f'TELEGRAF=True is set, but missing options {template_data}'
        raise TelegrafNotConfiguredError(emsg)

    logger.info('Configuring telegraf %s', template_data)
    process_template(TELEGRAF_TEMPLATE_PATH, TELEGRAF_CONFIG_PATH, template_data)

    ensure_telegraf_running(dutils)
    logger.info('Telegraf config updated, telegraf restarted')


def telegraf_config_processed() -> bool:
    with open(TELEGRAF_CONFIG_PATH) as f:
        return 'id: ' in f.read()


def update_monitoring_services(node_ip, node_id, skale, dutils: Optional[DockerUtils] = None):
    update_filebeat_service(node_ip, node_id, skale, dutils=dutils)
    if TELEGRAF:
        update_telegraf_service(node_ip, node_id, dutils=dutils)
