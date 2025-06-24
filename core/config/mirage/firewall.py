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

from typing import Dict, List


def get_node_ips_from_config(config: Dict | None) -> List[str]:
    if config is None:
        return []
    chain_nodes_config = config['skaleConfig']['sChain']['nodes']
    return [node_data['ip'] for node_data in chain_nodes_config]


def get_own_ip_from_config(config: Dict | None) -> str | None:
    if config is None:
        return None
    chain_nodes_config = config['skaleConfig']['sChain']['nodes']
    own_id = config['skaleConfig']['nodeInfo']['nodeID']
    for node_data in chain_nodes_config:
        if node_data['nodeID'] == own_id:
            return node_data['ip']
    return None
