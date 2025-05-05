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
from dataclasses import dataclass

from skale.types.rotation import Rotation
from skale.contracts.manager.schains import SchainStructure

from core.config.base_config import MirageConfig, SChainBaseConfig
from core.config.mirage.schain_info import MirageSChainInfo
from core.config.mirage.node_info import MirageCurrentNodeInfo, generate_mirage_current_node_info
from core.config.mirage.mirage_schain_node import generate_mirage_schain_nodes
from core.config.precompiled import get_precompiled_contracts_mirage
from core.config.schain.static_params import get_static_schain_info, get_static_node_info
from core.schains.limits import get_schain_type

from tools.configs import MIRAGE_CHAIN_NAME
from tools.configs.schains import (
    MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH,
    MAX_CONSENSUS_STORAGE_INF_VALUE,
)


logger = logging.getLogger(__name__)


@dataclass
class MirageSkaleConfig:
    node_info: MirageCurrentNodeInfo
    schain_info: MirageSChainInfo

    def to_dict(self):
        return {
            'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


def generate_mirage_config_with_manager() -> None:
    """Will be implemented in the future"""
    pass


def get_mirage_chain_id() -> str:
    return '0x3A6'  # TODO: Replace with actual logic to get the chain ID (or move to config file)


def generate_mirage_config(
    schain: SchainStructure,
    schain_nodes_with_schains: list,
    node_groups: dict,
    rotation_data: Rotation,
    node_id: int,
    ecdsa_key_name: str,
    schain_base_port: int,
    common_bls_public_keys: list[str],
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
) -> MirageConfig:
    logger.info('Generating Mirage config...')
    base_config = SChainBaseConfig(MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH)

    chain_id = get_mirage_chain_id()
    chain_id_int = int(chain_id, 16)

    dynamic_params = {'chainID': chain_id}
    accounts = get_precompiled_contracts_mirage()

    static_schain_info = get_static_schain_info(MIRAGE_CHAIN_NAME)

    contract_storage_limit = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value
    db_storage_limit = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value
    max_consensus_storage_bytes = MAX_CONSENSUS_STORAGE_INF_VALUE  # TODO: temporary value

    schain_nodes = generate_mirage_schain_nodes(
        schain_nodes_with_schains=schain_nodes_with_schains,
        schain_name=schain.name,
        rotation_id=rotation_data.rotation_counter,
        sync_node=False,
    )

    nodes = {
        rotation_data.freeze_until: schain_nodes,
        '': [],
    }  # TODO: Add second group here and tweak how we get the node lists

    schain_info = MirageSChainInfo(
        schain_id=chain_id_int,
        contract_storage_limit=contract_storage_limit,
        db_storage_limit=db_storage_limit,
        max_consensus_storage_bytes=max_consensus_storage_bytes,
        node_groups=node_groups,
        nodes=nodes,
        static_schain_info=static_schain_info,
    )

    schain_type = get_schain_type(schain.part_of_node)
    static_node_info = get_static_node_info(schain_type)
    nodes_in_schain = len(schain_nodes_with_schains)

    current_node_info = generate_mirage_current_node_info(
        node_id=node_id,
        ecdsa_key_name=ecdsa_key_name,
        static_node_info=static_node_info,
        schain=schain,
        rotation_id=rotation_data.rotation_counter,
        schain_base_port=schain_base_port,
        nodes_in_schain=nodes_in_schain,
        common_bls_public_keys=common_bls_public_keys,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
    )

    skale_config = MirageSkaleConfig(schain_info=schain_info, node_info=current_node_info)

    return MirageConfig(
        seal_engine=base_config.config['sealEngine'],
        params={**base_config.config['params'], **dynamic_params},
        unddos=base_config.config['unddos'],
        genesis=base_config.config['genesis'],
        accounts=accounts,
        skale_config=skale_config,
    )
