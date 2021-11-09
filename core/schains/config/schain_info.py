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

from core.schains.limits import get_schain_limit
from core.schains.types import MetricType


@dataclass
class SChainInfo:
    """Dataclass that represents sChain key of the skaleConfig section"""
    schain_id: int
    name: str
    owner: str

    contract_storage_limit: int
    db_storage_limit: int

    snapshot_interval_sec: int
    empty_block_interval_ms: int

    free_contract_deployment: bool

    max_consensus_storage_bytes: int
    max_skaled_leveldb_storage_bytes: int
    max_file_storage_bytes: int
    max_reserved_storage_bytes: int

    previous_public_keys_info: list
    nodes: list

    def to_dict(self):
        """Returns camel-case representation of the SChainInfo object"""
        return {
            'schainID': self.schain_id,
            'schainName': self.name,
            'schainOwner': self.owner,
            'contractStorageLimit': self.contract_storage_limit,
            'dbStorageLimit': self.db_storage_limit,
            'snapshotIntervalSec': self.snapshot_interval_sec,
            'emptyBlockIntervalMs': self.empty_block_interval_ms,
            'freeContractDeployment': self.free_contract_deployment,
            'maxConsensusStorageBytes': self.max_consensus_storage_bytes,
            'maxSkaledLeveldbStorageBytes': self.max_skaled_leveldb_storage_bytes,
            'maxFileStorageBytes': self.max_file_storage_bytes,
            'maxReservedStorageBytes': self.max_reserved_storage_bytes,
            # 'previousKeysInfo': self.previous_public_keys_info,
            'nodes': self.nodes
        }


def generate_schain_info(schain_id: int, schain: dict, static_schain_params: dict,
                         previous_public_keys_info: list, nodes: dict) -> SChainInfo:
    volume_limits = get_schain_limit(schain, MetricType.volume_limits)
    leveldb_limits = get_schain_limit(schain, MetricType.leveldb_limits)
    contract_storage_limit = leveldb_limits['contract_storage']
    db_storage_limit = leveldb_limits['db_storage']

    return SChainInfo(
        schain_id=schain_id,
        name=schain['name'],
        owner=schain['owner'],
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        previous_public_keys_info=previous_public_keys_info,
        nodes=nodes,
        **volume_limits,
        **static_schain_params['schain']
    )
