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

from core.schains.limits import get_allocation_type_name, get_schain_limit, get_schain_type
from core.schains.types import MetricType

from tools.configs.schains import MAX_CONSENSUS_STORAGE_INF_VALUE


@dataclass
class SChainInfo:
    """Dataclass that represents sChain key of the skaleConfig section"""
    schain_id: int
    name: str
    block_author: str

    contract_storage_limit: int
    db_storage_limit: int

    max_consensus_storage_bytes: int
    max_skaled_leveldb_storage_bytes: int
    max_file_storage_bytes: int
    max_reserved_storage_bytes: int

    node_groups: dict
    nodes: list
    static_schain_info: dict

    multitransaction_mode: bool

    def to_dict(self):
        """Returns camel-case representation of the SChainInfo object"""
        return {
            'schainID': self.schain_id,
            'schainName': self.name,
            'blockAuthor': self.block_author,
            'contractStorageLimit': self.contract_storage_limit,
            'dbStorageLimit': self.db_storage_limit,
            'maxConsensusStorageBytes': self.max_consensus_storage_bytes,
            'maxSkaledLeveldbStorageBytes': self.max_skaled_leveldb_storage_bytes,
            'maxFileStorageBytes': self.max_file_storage_bytes,
            'maxReservedStorageBytes': self.max_reserved_storage_bytes,
            'nodeGroups': self.node_groups,
            'multiTransactionMode': self.multitransaction_mode,
            'nodes': self.nodes,
            **self.static_schain_info
        }


def generate_schain_info(
    schain_id: int,
    schain: dict,
    on_chain_etherbase: str,
    static_schain_info: dict,
    node_groups: dict,
    nodes: dict,
    sync_node: bool,
    archive: bool
) -> SChainInfo:
    schain_type = get_schain_type(schain.part_of_node)
    allocation_type_name = get_allocation_type_name(schain.options.allocation_type)
    volume_limits = get_schain_limit(schain_type, MetricType.volume_limits)[allocation_type_name]
    if sync_node and archive:
        volume_limits['max_consensus_storage_bytes'] = MAX_CONSENSUS_STORAGE_INF_VALUE
    leveldb_limits = get_schain_limit(schain_type, MetricType.leveldb_limits)[allocation_type_name]
    contract_storage_limit = leveldb_limits['contract_storage']
    db_storage_limit = leveldb_limits['db_storage']

    return SChainInfo(
        schain_id=schain_id,
        name=schain.name,
        block_author=on_chain_etherbase,
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        node_groups=node_groups,
        nodes=nodes,
        multitransaction_mode=schain.options.multitransaction_mode,
        static_schain_info=static_schain_info,
        **volume_limits
    )
