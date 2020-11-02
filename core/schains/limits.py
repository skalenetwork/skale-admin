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

from core.schains.types import SchainType, ContainerType, MetricType
from tools.helper import read_json
from tools.configs.resource_allocation import RESOURCE_ALLOCATION_FILEPATH


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


def get_schain_limit(schain: dict, metric_type: MetricType) -> int:
    alloc = _get_resource_allocation_info()
    schain_type = get_schain_type(schain)
    return get_limit(metric_type, schain_type, ContainerType.schain, alloc)


def get_ima_limit(schain: dict, metric_type: MetricType) -> int:
    alloc = _get_resource_allocation_info()
    schain_type = get_schain_type(schain)
    return get_limit(metric_type, schain_type, ContainerType.ima, alloc)


def get_schain_container_limits(schain):
    alloc = _get_resource_allocation_info()
    schain_type = get_schain_type(schain)
    cpu_limit = get_limit(MetricType.cpu_shares, schain_type, ContainerType.schain, alloc)
    mem_limit = get_limit(MetricType.mem, schain_type, ContainerType.schain, alloc)
    disk_limit = get_limit(MetricType.disk, schain_type, ContainerType.schain, alloc)
    volume_limits = get_limit(MetricType.volume_limits, schain_type, ContainerType.schain, alloc)
    storage_limit = get_limit(MetricType.storage_limit, schain_type, ContainerType.schain, alloc)
    return cpu_limit, mem_limit, disk_limit, volume_limits, storage_limit


def get_ima_container_limits(schain):
    alloc = _get_resource_allocation_info()
    schain_type = get_schain_type(schain)
    cpu_limit = get_limit(MetricType.cpu_shares, schain_type, ContainerType.schain, alloc)
    mem_limit = get_limit(MetricType.mem, schain_type, ContainerType.schain, alloc)
    return cpu_limit, mem_limit


def get_schain_type(schain):
    part_of_node = int(schain['partOfNode'])
    return SchainType(part_of_node)


def _get_resource_allocation_info():
    return read_json(RESOURCE_ALLOCATION_FILEPATH)


def _cpu_to_nanocpu(cpu_limit):
    return int(cpu_limit * 10 ** 9)
