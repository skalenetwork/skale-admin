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

from skale.dataclasses.schain_options import AllocationType

from core.schains.types import SchainType, ContainerType, MetricType
from tools.helper import read_json
from tools.configs.resource_allocation import (
    RESOURCE_ALLOCATION_FILEPATH, FILESTORAGE_LIMIT_OPTION_NAME
)


def get_schain_type(schain_part_of_node: int) -> SchainType:
    """
    Returns SKALE chain type based on part_of_node value from the sChain structure.
    """
    if isinstance(schain_part_of_node, str):
        schain_part_of_node = int(schain_part_of_node)
    return SchainType(schain_part_of_node)


def get_allocation_type_name(allocation_type: AllocationType) -> str:
    return allocation_type.name.lower()


def get_limit(metric_type: MetricType, schain_type: SchainType, container_type: ContainerType,
              resource_allocation: dict) -> int:
    """
    Get allocation option from the resources allocation file

    :param metric: Type of the metric to get
    :type metric: MetricType
    :param schain_type: Type of the sChain
    :type schain_type: SchainType
    :param container_type: Type of the container
    :type container_type: ContainerType
    :param resource_allocation: Resources allocation dict
    :type resource_allocation: dict

    :returns: Limit value
    :rtype: int
    """
    return resource_allocation[container_type.name][metric_type.name][schain_type.name]


def get_schain_limit(schain_type: SchainType, metric_type: MetricType) -> dict:
    alloc = _get_resource_allocation_info()
    return get_limit(metric_type, schain_type, ContainerType.schain, alloc)


def get_ima_limit(schain_type: SchainType, metric_type: MetricType) -> int:
    alloc = _get_resource_allocation_info()
    return get_limit(metric_type, schain_type, ContainerType.ima, alloc)


def get_fs_allocated_storage(schain_type: SchainType, allocation_type: AllocationType) -> str:
    allocation_type_name = get_allocation_type_name(allocation_type)
    volume_limits = get_schain_limit(schain_type, MetricType.volume_limits)[allocation_type_name]
    return volume_limits[FILESTORAGE_LIMIT_OPTION_NAME]


def _get_resource_allocation_info():
    return read_json(RESOURCE_ALLOCATION_FILEPATH)
