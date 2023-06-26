#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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

import json
import logging

from typing import List, Optional, Tuple

from skale import Skale

from .types import IpRange
from .rule_controller import IptablesSChainRuleController


logger = logging.getLogger(__name__)


def get_default_rule_controller(
    name: str,
    base_port: Optional[int] = None,
    own_ip: Optional[str] = None,
    node_ips: List[str] = [],
    sync_agent_ranges: Optional[List[IpRange]] = []
) -> IptablesSChainRuleController:
    sync_agent_ranges = sync_agent_ranges or []
    logger.info('Creating rule controller for %s', name)
    logger.debug('Rule controller ranges for %s: %s', name, sync_agent_ranges)
    return IptablesSChainRuleController(
        name=name,
        base_port=base_port,
        own_ip=own_ip,
        node_ips=node_ips,
        sync_ip_ranges=sync_agent_ranges
    )


def get_sync_agent_ranges(skale: Skale) -> List[IpRange]:
    sync_agent_ranges = []
    rnum = skale.sync_manager.get_ip_ranges_number()
    for i in range(rnum):
        sync_agent_ranges.append(skale.sync_manager.get_ip_range_by_index(i))
    return sorted(sync_agent_ranges)


def save_sync_ranges(sync_agent_ranges: List[IpRange], path: str) -> None:
    output = {'ranges': [tuple(r) for r in sync_agent_ranges]}
    with open(path, 'w') as out_file:
        json.dump(output, out_file)


def ranges_from_plain_tuples(plain_ranges: List[Tuple]) -> List[IpRange]:
    return list(sorted(map(lambda r: IpRange(r) for r in plain_ranges)))
