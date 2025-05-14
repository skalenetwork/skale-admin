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

import socket
import logging
from dataclasses import dataclass
from typing import Dict

from skale.types.rotation import NodesGroup, Rotation
from skale.types.node import Node as SkaleNode, NodeWithSchains, MirageNode, NodeId
from skale.utils.web3_utils import public_key_to_address, to_checksum_address

from core.config.base_config import MirageConfig, SChainBaseConfig
from core.config.mirage.schain_info import MirageChainInfo
from core.config.mirage.node_info import MirageCurrentNodeInfo, generate_mirage_current_node_info
from core.config.mirage.mirage_schain_node import generate_mirage_chain_nodes
from core.config.precompiled import get_precompiled_contracts_mirage
from core.config.schain.static_params import (
    get_static_schain_info_mirage,
    get_static_node_info_mirage,
)
from core.config.schain.static_params import get_static_chain_id_mirage

from tools.configs.schains import MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH

logger = logging.getLogger(__name__)


@dataclass
class MirageSkaleConfig:
    node_info: MirageCurrentNodeInfo
    schain_info: MirageChainInfo

    def to_dict(self):
        return {
            'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


def generate_mirage_config_with_manager() -> None:
    """Will be implemented in the future"""
    pass


def skale_node_to_mirage_node_adapter(skale_node: SkaleNode, node_id: NodeId) -> MirageNode:
    return MirageNode(
        id=node_id,
        ip=skale_node['ip'],
        ip_str=socket.inet_ntoa(skale_node['ip']),
        port=skale_node['port'],
        domain_name=skale_node['domain_name'],
        address=to_checksum_address(public_key_to_address(skale_node['publicKey'])),
        name=skale_node['name'],
        public_key=skale_node['publicKey'],
    )


def generate_mirage_config_adapter(
    skale_node: SkaleNode,
    node_id: NodeId,
    schain_nodes_with_schains: list[NodeWithSchains],
    node_groups: Dict[int, NodesGroup],
    rotation_data: Rotation,
    ecdsa_key_name: str,
    common_bls_public_keys: list[str],
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
):
    node = skale_node_to_mirage_node_adapter(skale_node, node_id)
    committee_nodes = [
        skale_node_to_mirage_node_adapter(schain_node, schain_node['id'])
        for schain_node in schain_nodes_with_schains
    ]
    return generate_mirage_config(
        node=node,
        committee_nodes=committee_nodes,
        node_groups=node_groups,
        group_index=rotation_data.rotation_counter,
        ecdsa_key_name=ecdsa_key_name,
        common_bls_public_keys=common_bls_public_keys,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
    )


def generate_mirage_config(
    node: MirageNode,
    committee_nodes: list[MirageNode],
    node_groups: Dict[int, NodesGroup],
    group_index: int,
    ecdsa_key_name: str,
    common_bls_public_keys: list[str],
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
) -> MirageConfig:
    logger.info('Generating Mirage config...')
    base_config = SChainBaseConfig(MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH)

    chain_id = get_static_chain_id_mirage()
    chain_id_int = int(chain_id, 16)

    dynamic_params = {'chainID': chain_id}
    accounts = get_precompiled_contracts_mirage()

    static_schain_info = get_static_schain_info_mirage()

    chain_nodes = generate_mirage_chain_nodes(
        committee_nodes=committee_nodes,
        rotation_id=group_index,
        sync_node=False,
    )

    schain_info = MirageChainInfo(
        schain_id=chain_id_int,
        node_groups=node_groups,
        nodes=chain_nodes,
        static_schain_info=static_schain_info,
    )

    static_node_info = get_static_node_info_mirage()
    nodes_in_chain = len(committee_nodes)

    current_node_info = generate_mirage_current_node_info(
        node_id=node.id,
        ecdsa_key_name=ecdsa_key_name,
        static_node_info=static_node_info,
        group_index=group_index,
        port=node.port,
        nodes_in_chain=nodes_in_chain,
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
