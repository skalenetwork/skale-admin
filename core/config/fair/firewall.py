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

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


def get_node_ips_from_config(config: Dict | None, current_ts: int) -> List[str]:
    if config is None:
        return []
    committee_nodes_in_scope = config['skaleConfig']['sChain']['nodes']
    ts_a, ts_b = sorted(map(int, committee_nodes_in_scope.keys()))
    group_a = committee_nodes_in_scope[str(ts_a)]['group']
    group_b = committee_nodes_in_scope[str(ts_b)]['group']
    if current_ts <= ts_b:
        return [
            *(node_data['ip'] for node_data in group_a),
            *(node_data['ip'] for node_data in group_b),
        ]
    else:
        return [node_data['ip'] for node_data in group_b]


def get_own_ip_from_config(config: Dict | None, current_ts: int) -> str | None:
    if config is None:
        return None
    own_id = config['skaleConfig']['nodeInfo']['nodeID']
    committee_nodes_in_scope = config['skaleConfig']['sChain']['nodes']
    ts_a, ts_b = sorted(map(int, committee_nodes_in_scope.keys()))
    group_a = committee_nodes_in_scope[str(ts_a)]['group']
    group_b = committee_nodes_in_scope[str(ts_b)]['group']
    if current_ts <= ts_b:
        current_group = group_a
    else:
        current_group = group_b

    for node_data in current_group:
        if node_data['nodeID'] == own_id:
            return node_data['ip']
    # For fair it is valid situation, since previous or next committee may not have this node.
    return None
