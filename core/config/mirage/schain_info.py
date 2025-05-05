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

from tools.configs.schains import MAX_CONSENSUS_STORAGE_INF_VALUE, MAX_HISTORIC_STATE_DB_SIZE


@dataclass
class MirageSChainInfo:
    schain_id: int

    contract_storage_limit: int
    db_storage_limit: int
    max_consensus_storage_bytes: int

    node_groups: dict
    nodes: dict
    static_schain_info: dict

    max_historic_state_db_size: int | None = None

    def to_dict(self):
        data = {
            'schainID': self.schain_id,
            'contractStorageLimit': self.contract_storage_limit,
            'dbStorageLimit': self.db_storage_limit,
            'maxConsensusStorageBytes': self.max_consensus_storage_bytes,
            'nodeGroups': self.node_groups,
            'multiTransactionMode': True,
            'nodes': self.nodes,
            **self.static_schain_info,
        }
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
) -> MirageSChainInfo:
    contract_storage_limit = 10  # todo: from config
    db_storage_limit = 10  # todo: from config

    if sync_node and archive:
        max_consensus_storage_bytes = MAX_CONSENSUS_STORAGE_INF_VALUE
        max_historic_state_db_size = MAX_HISTORIC_STATE_DB_SIZE
    else:
        max_historic_state_db_size = None
        max_consensus_storage_bytes = 10  # todo: from config

    return MirageSChainInfo(
        schain_id=schain_id,
        node_groups=node_groups,
        nodes=nodes,
        static_schain_info=static_schain_info,
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        max_consensus_storage_bytes=max_consensus_storage_bytes,
        max_historic_state_db_size=max_historic_state_db_size,
    )
