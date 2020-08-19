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

from core.schains.volume import (get_resource_allocation_info, get_allocation_option_name,
                                 get_allocation_part_name)


@dataclass
class SChainInfo:
    """Dataclass that represents sChain key of the skaleConfig section"""
    schain_id: int
    name: str
    owner: str
    storage_limit: int

    snapshot_interval_ms: int
    empty_block_interval_ms: int

    max_consensus_storage_bytes: int
    max_skaled_leveldb_storage_bytes: int
    max_file_storage_bytes: int
    max_reserved_storage_bytes: int

    nodes: list

    def to_dict(self):
        """Returns camel-case representation of the SChainInfo object"""
        return {
            'schainID': self.schain_id,
            'schainName': self.name,
            'schainOwner': self.owner,
            'storageLimit': self.storage_limit,
            'snapshotIntervalMs': self.snapshot_interval_ms,
            'emptyBlockIntervalMs': self.empty_block_interval_ms,
            'maxConsensusStorageBytes': self.max_consensus_storage_bytes,
            'maxSkaledLeveldbStorageBytes': self.max_skaled_leveldb_storage_bytes,
            'maxFileStorageBytes': self.max_file_storage_bytes,
            'maxReservedStorageBytes': self.max_reserved_storage_bytes,
            'nodes': self.nodes
        }


def generate_schain_info(schain_id: int, schain: dict, static_schain_params: dict,
                         nodes: dict) -> SChainInfo:
    resource_allocation = get_resource_allocation_info()
    schain_size_name = get_allocation_option_name(schain)
    allocation_part_name = get_allocation_part_name(schain)
    schin_internal_limits = resource_allocation['schain'][allocation_part_name]

    return SChainInfo(
        schain_id=schain_id,
        name=schain['name'],
        owner=schain['owner'],
        storage_limit=resource_allocation['schain']['storage_limit'][schain_size_name],
        nodes=nodes,
        **schin_internal_limits,
        **static_schain_params['schain']
    )
