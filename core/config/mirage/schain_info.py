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

from dataclasses import dataclass
from typing import Dict
from skale.types.rotation import NodesGroup
from core.config.mirage.committee import CommitteeInfo
from core.config.schain.static_params import get_static_chain_name_mirage
from tools.configs.schains import MAX_HISTORIC_STATE_DB_SIZE


@dataclass
class MirageChainInfo:
    schain_id: int

    node_groups: Dict[int, NodesGroup]
    nodes: dict[int, CommitteeInfo]
    static_schain_info: dict

    max_historic_state_db_size: int | None = None

    def to_dict(self):
        data = {
            'schainID': self.schain_id,
            'schainName': get_static_chain_name_mirage(),
            'nodeGroups': self.node_groups,
            'multiTransactionMode': True,
        }
        nodes_with_str_key = {
            str(ts): committee_info.to_dict() for ts, committee_info in self.nodes.items()
        }
        data.update({'nodes': nodes_with_str_key})
        data.update(**self.static_schain_info)
        if self.max_historic_state_db_size:
            data.update({'maxHistoricStateDbSize': self.max_historic_state_db_size})
        return data


def generate_schain_info(
    schain_id: int,
    static_schain_info: dict,
    node_groups: dict,
    nodes: list,
    sync_node: bool,
    archive: bool,
) -> MirageChainInfo:
    # TODOd: fix override from config
    if sync_node and archive:
        # max_consensus_storage_bytes = MAX_CONSENSUS_STORAGE_INF_VALUE
        max_historic_state_db_size = MAX_HISTORIC_STATE_DB_SIZE
    else:
        max_historic_state_db_size = None
        # max_consensus_storage_bytes = 10  # todo: from config

    return MirageChainInfo(
        schain_id=schain_id,
        node_groups=node_groups,
        nodes=nodes,
        static_schain_info=static_schain_info,
        max_historic_state_db_size=max_historic_state_db_size,
    )
