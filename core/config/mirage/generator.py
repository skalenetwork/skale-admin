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
import socket
from dataclasses import dataclass
from typing import Dict

from skale import MirageManager
from skale.mirage_config import generate_committee_history, get_nodes_from_last_two_committees
from skale.types.committee import CommitteeGroup
from skale.types.node import MirageNode, NodeId, NodeWithSchains
from skale.types.node import Node as SkaleNode
from skale.types.rotation import NodesGroup
from skale.types.committee import CommitteeIndex, TimeStamp
from skale.utils.web3_utils import public_key_to_address, to_checksum_address

from core.config.base import MirageConfig, SChainBaseConfig
from core.config.mirage.committee import generate_committee_info
from core.config.mirage.node_info import MirageCurrentNodeInfo, generate_mirage_current_node_info
from core.config.mirage.schain_info import MirageChainInfo
from core.config.precompiled import get_precompiled_contracts_mirage
from core.config.schain.static_params import (
    get_static_chain_id_mirage,
    get_static_node_info_mirage,
    get_static_schain_info_mirage,
)
from tools.configs.schains import MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH
from tools.helper import cast_manager_to_mirage_node_id

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


def generate_mirage_config_with_manager(
    mirage: MirageManager,
    node_id: NodeId,
    ecdsa_key_name: str,
    is_committee_node: bool,
    archive: bool,
    catchup: bool,
) -> MirageConfig:
    node = mirage.nodes.get(cast_manager_to_mirage_node_id(node_id))

    committee_nodes_in_scope = get_nodes_from_last_two_committees(mirage)
    node_groups = generate_committee_history(mirage=mirage)

    return generate_mirage_config(
        node=node,
        committee_info_from_manager=committee_nodes_in_scope,
        node_groups=node_groups,
        ecdsa_key_name=ecdsa_key_name,
        is_committee_node=is_committee_node,
        archive=archive,
        catchup=catchup,
    )


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
    chain_start_ts: int,
    schain_nodes_with_schains: list[NodeWithSchains],
    node_groups: Dict[int, NodesGroup],
    ecdsa_key_name: str,
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
):
    node = skale_node_to_mirage_node_adapter(skale_node, node_id)
    committee_nodes = [
        skale_node_to_mirage_node_adapter(schain_node, schain_node['id'])
        for schain_node in schain_nodes_with_schains
    ]

    committee_info_from_manager: list[CommitteeGroup] = [
        {'ts': TimeStamp(0), 'index': CommitteeIndex(0), 'group': committee_nodes},
        {'ts': TimeStamp(chain_start_ts), 'index': CommitteeIndex(0), 'group': committee_nodes},
    ]
    return generate_mirage_config(
        node=node,
        committee_info_from_manager=committee_info_from_manager,
        node_groups=node_groups,
        ecdsa_key_name=ecdsa_key_name,
        is_committee_node=True,
        archive=archive,
        catchup=catchup,
    )


def generate_mirage_config(
    node: MirageNode,
    committee_info_from_manager: list[CommitteeGroup],
    node_groups: Dict[int, NodesGroup],
    ecdsa_key_name: str,
    is_committee_node: bool,
    archive: bool = False,
    catchup: bool = False,
) -> MirageConfig:
    logger.info('Generating Mirage config...')
    base_config = SChainBaseConfig(MIRAGE_BASE_SCHAIN_CONFIG_FILEPATH)

    chain_id = get_static_chain_id_mirage()
    chain_id_int = int(chain_id, 16)

    dynamic_params = {'chainID': chain_id}
    accounts = {
        **base_config.config['accounts'],
        **get_precompiled_contracts_mirage(),
    }

    static_schain_info = get_static_schain_info_mirage()
    committee_info = {}

    committee_info = generate_committee_info(
        committee_info_from_manager=committee_info_from_manager,
        node_id=node.id,
    )

    schain_info = MirageChainInfo(
        schain_id=chain_id_int,
        node_groups=node_groups,
        nodes=committee_info,
        static_schain_info=static_schain_info,
    )

    static_node_info = get_static_node_info_mirage()

    current_node_info = generate_mirage_current_node_info(
        node_id=node.id,
        ecdsa_key_name=ecdsa_key_name,
        static_node_info=static_node_info,
        port=node.port,
        is_committee_node=is_committee_node,
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
