#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

import random
import time
from typing import Dict, List

from skale.types.node import NodeId


def get_current_nodes(config: Dict) -> List[dict]:
    if config is None:
        return []
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']

    current_timestamp = int(time.time())

    timestamps = schain_nodes_config.keys()
    needed_timestamp = None
    for timestamp in sorted(timestamps, key=int):
        if int(timestamp) > current_timestamp:
            needed_timestamp = timestamp
            break

    if needed_timestamp is None:
        needed_timestamp = max(timestamps)
    return schain_nodes_config[needed_timestamp]['group']


def is_node_in_current_config_group(config: Dict | None, node_id: NodeId) -> bool:
    if config is None:
        return False
    group_data = get_current_nodes(config)
    if len(group_data) == 0:
        return False
    return any(node_data['nodeID'] == node_id for node_data in group_data)


def get_node_ips_from_config(config: Dict) -> List[str]:
    group_data = get_current_nodes(config)
    if len(group_data) == 0:
        return []
    return [node_data['ip'] for node_data in group_data]


def random_timestamp_between(start: int, end: int) -> int:
    return random.randint(min(start, end), max(start, end))
