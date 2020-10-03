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

from core.schains.types import SchainTypes
from tools.helper import read_json
from tools.configs.resource_allocation import RESOURCE_ALLOCATION_FILEPATH
from tools.configs.schains import FILESTORAGE_ARTIFACTS_FILEPATH
from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


def init_data_volume(schain, dutils=None):
    dutils = dutils or DockerUtils()
    schain_name = schain['name']

    if dutils.is_data_volume_exists(schain_name):
        logger.debug(f'Volume already exists: {schain_name}')
        return

    logger.info(f'Creating volume for schain: {schain_name}')
    option_name = get_allocation_option_name(schain)
    resource_allocation = get_resource_allocation_info()
    volume_size = resource_allocation['disk'][f'part_{option_name}']

    return dutils.create_data_volume(schain_name, volume_size)


def get_container_limits(schain):
    size = get_allocation_option_name(schain)
    cpu_shares_limit = get_allocation_option('cpu_shares', size)
    return cpu_shares_limit, get_allocation_option('mem', size)


def cpu_to_nanocpu(cpu_limit):
    return int(cpu_limit * 10 ** 9)


def get_allocation_option(metric, size):
    resource_allocation = get_resource_allocation_info()
    return resource_allocation[metric][f'part_{size}']


def get_allocation_option_name(schain):
    part_of_node = int(schain['partOfNode'])
    return SchainTypes(part_of_node).name


def get_allocation_part_name(schain):
    return f'part_{get_allocation_option_name(schain)}'


def get_resource_allocation_info():
    return read_json(RESOURCE_ALLOCATION_FILEPATH)


def get_filestorage_info():
    return read_json(FILESTORAGE_ARTIFACTS_FILEPATH)


def get_schain_volume_config(name, mount_path, mode='Z'):
    return {f'{name}': {'bind': mount_path, 'mode': 'Z'}}
