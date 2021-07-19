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

from core.schains.limits import get_schain_limit
from core.schains.types import MetricType
from tools.configs.containers import (
    SHARED_SPACE_VOLUME_NAME,
    SHARED_SPACE_CONTAINER_PATH
)

from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


def init_data_volume(schain, dutils=None):
    dutils = dutils or DockerUtils()
    schain_name = schain['name']

    if dutils.is_data_volume_exists(schain_name):
        logger.debug(f'Volume already exists: {schain_name}')
        return

    logger.info(f'Creating volume for schain: {schain_name}')
    disk_limit = get_schain_limit(schain, MetricType.disk)
    return dutils.create_data_volume(schain_name, disk_limit)


def get_schain_volume_config(name, mount_path, mode=None):
    mode = mode or 'rw'
    config = {
        f'{name}': {'bind': mount_path, 'mode': mode},
        SHARED_SPACE_VOLUME_NAME: {
            'bind': SHARED_SPACE_CONTAINER_PATH,
            'mode': mode
        }
    }
    return config
