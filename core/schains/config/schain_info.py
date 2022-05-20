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

from dataclasses import dataclass

from core.schains.limits import get_schain_limit, get_schain_type
from core.schains.types import MetricType


@dataclass
class SChainInfo:
    """Dataclass that represents sChain key of the skaleConfig section"""
    schain_id: int
    name: str
    block_author: str

    contract_storage_limit: int
    db_storage_limit: int

    snapshot_interval_sec: int
    empty_block_interval_ms: int

    free_contract_deployment: bool

    max_consensus_storage_bytes: int
    max_skaled_leveldb_storage_bytes: int
    max_file_storage_bytes: int
    max_reserved_storage_bytes: int

    node_groups: dict
    nodes: list

    multitransaction_mode: bool

    def to_dict(self):
        """Returns camel-case representation of the SChainInfo object"""
        return {
            'schainID': self.schain_id,
            'schainName': self.name,
            'blockAuthor': self.block_author,
            'contractStorageLimit': self.contract_storage_limit,
            'dbStorageLimit': self.db_storage_limit,
            'snapshotIntervalSec': self.snapshot_interval_sec,
            'emptyBlockIntervalMs': self.empty_block_interval_ms,
            'freeContractDeployment': self.free_contract_deployment,
            'maxConsensusStorageBytes': self.max_consensus_storage_bytes,
            'maxSkaledLeveldbStorageBytes': self.max_skaled_leveldb_storage_bytes,
            'maxFileStorageBytes': self.max_file_storage_bytes,
            'maxReservedStorageBytes': self.max_reserved_storage_bytes,
            'nodeGroups': self.node_groups,
            'multiTransactionMode': self.multitransaction_mode,
            'nodes': self.nodes
        }


def generate_schain_info(schain_id: int, schain: dict, on_chain_etherbase: str,
                         static_schain_params: dict, node_groups: dict,
                         nodes: dict, sync_node: bool) -> SChainInfo:
    schain_type = get_schain_type(schain['partOfNode'], sync_node=sync_node)
    volume_limits = get_schain_limit(schain_type, MetricType.volume_limits)
    leveldb_limits = get_schain_limit(schain_type, MetricType.leveldb_limits)
    contract_storage_limit = leveldb_limits['contract_storage']
    db_storage_limit = leveldb_limits['db_storage']

    return SChainInfo(
        schain_id=schain_id,
        name=schain['name'],
        block_author=on_chain_etherbase,
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        node_groups=node_groups,
        nodes=nodes,
        multitransaction_mode=schain['multitransactionMode'],
        **volume_limits,
        **static_schain_params['schain']
    )
