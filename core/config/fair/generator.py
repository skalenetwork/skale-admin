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

from skale import FairManager
from skale.fair_config import generate_committee_history, get_nodes_from_last_two_committees
from skale.types.committee import Committee, CommitteeGroup, CommitteeIndex, Timestamp
from skale.types.dkg import DkgId, Fp2Point, G2Point
from skale.types.node import FairNodeForChainConfig, NodeId, NodeWithSchains
from skale.types.node import Node as SkaleNode
from skale.types.rotation import NodesGroup
from skale.utils.web3_utils import public_key_to_address, to_checksum_address

from core.config.base import FairConfig, SChainBaseConfig
from core.config.fair.committee import generate_committee_info
from core.config.fair.node_info import FairCurrentNodeInfo, generate_fair_current_node_info
from core.config.fair.schain_info import FairChainInfo
from core.config.precompiled import get_precompiled_contracts_fair
from core.config.schain.static_params import (
    get_static_chain_id_fair,
    get_static_node_info_fair,
    get_static_schain_info_fair,
)
from tools.configs.schains import FAIR_BASE_SCHAIN_CONFIG_FILEPATH
from tools.configs.web3 import ZERO_ADDRESS
from tools.helper import cast_manager_to_fair_node_id

logger = logging.getLogger(__name__)


@dataclass
class FairSkaleConfig:
    node_info: FairCurrentNodeInfo
    schain_info: FairChainInfo

    def to_dict(self):
        return {
            'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


def generate_fair_config_with_manager(
    fair: FairManager,
    node_id: NodeId,
    ecdsa_key_name: str,
    is_committee_node: bool,
    archive: bool,
    catchup: bool,
) -> FairConfig:
    node = fair.nodes.get(cast_manager_to_fair_node_id(node_id))

    committee_nodes_in_scope = get_nodes_from_last_two_committees(fair)
    node_groups = generate_committee_history(fair=fair)

    return generate_fair_config(
        node=node,
        committee_info_from_manager=committee_nodes_in_scope,
        node_groups=node_groups,
        ecdsa_key_name=ecdsa_key_name,
        is_committee_node=is_committee_node,
        archive=archive,
        catchup=catchup,
    )


def skale_node_to_fair_node_adapter(
    skale_node: SkaleNode, node_id: NodeId
) -> FairNodeForChainConfig:
    return FairNodeForChainConfig(
        id=node_id,
        ip=skale_node['ip'],
        ip_str=socket.inet_ntoa(skale_node['ip']),
        port=skale_node['port'],
        domain_name=skale_node['domain_name'],
        address=to_checksum_address(public_key_to_address(skale_node['publicKey'])),
        # This function is only used during boot phase, so all nodes are in initial committee
        # Therefore all nodes have ZERO_ADDRESS as reward wallet address
        reward_wallet_address=to_checksum_address(ZERO_ADDRESS),
        name=skale_node['name'],
        public_key=skale_node['publicKey'],
    )


def generate_fair_config_adapter(
    skale_node: SkaleNode,
    node_id: NodeId,
    chain_start_ts: int,
    schain_nodes_with_schains: list[NodeWithSchains],
    node_groups: Dict[int, NodesGroup],
    ecdsa_key_name: str,
    passive_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
):
    node = skale_node_to_fair_node_adapter(skale_node, node_id)
    committee_nodes = [
        skale_node_to_fair_node_adapter(schain_node, schain_node['id'])
        for schain_node in schain_nodes_with_schains
    ]

    committee_info_from_manager: list[CommitteeGroup] = [
        {
            'ts': Timestamp(0),
            'index': CommitteeIndex(0),
            'staking_contract_address': to_checksum_address(ZERO_ADDRESS),
            'group': committee_nodes,
            'committee': Committee(
                node_ids=[node.id for node in committee_nodes],
                dkg_id=DkgId(0),
                common_public_key=G2Point(Fp2Point(a=1, b=2), Fp2Point(a=3, b=4)),
                starting_timestamp=Timestamp(0),
            ),
        },
        {
            'ts': Timestamp(chain_start_ts),
            'index': CommitteeIndex(0),
            'staking_contract_address': to_checksum_address(ZERO_ADDRESS),
            'group': committee_nodes,
            'committee': Committee(
                node_ids=[node.id for node in committee_nodes],
                dkg_id=DkgId(0),
                common_public_key=G2Point(Fp2Point(a=1, b=2), Fp2Point(a=3, b=4)),
                starting_timestamp=Timestamp(0),
            ),
        },
    ]
    return generate_fair_config(
        node=node,
        committee_info_from_manager=committee_info_from_manager,
        node_groups=node_groups,
        ecdsa_key_name=ecdsa_key_name,
        is_committee_node=True,
        archive=archive,
        catchup=catchup,
    )


def generate_fair_config(
    node: FairNodeForChainConfig,
    committee_info_from_manager: list[CommitteeGroup],
    node_groups: Dict[int, NodesGroup],
    ecdsa_key_name: str,
    is_committee_node: bool,
    archive: bool = False,
    catchup: bool = False,
) -> FairConfig:
    logger.info('Generating Fair config...')
    base_config = SChainBaseConfig(FAIR_BASE_SCHAIN_CONFIG_FILEPATH)

    chain_id = get_static_chain_id_fair()
    chain_id_int = int(chain_id, 16)

    dynamic_params = {'chainID': chain_id}
    accounts = {
        **base_config.config['accounts'],
        **get_precompiled_contracts_fair(),
    }

    static_schain_info = get_static_schain_info_fair()
    committee_info = {}

    committee_info = generate_committee_info(
        committee_info_from_manager=committee_info_from_manager,
        node_id=node.id,
    )

    schain_info = FairChainInfo(
        schain_id=chain_id_int,
        node_groups=node_groups,
        nodes=committee_info,
        static_schain_info=static_schain_info,
    )

    static_node_info = get_static_node_info_fair()

    current_node_info = generate_fair_current_node_info(
        node_id=node.id,
        ecdsa_key_name=ecdsa_key_name,
        static_node_info=static_node_info,
        port=node.port,
        is_committee_node=is_committee_node,
        archive=archive,
        catchup=catchup,
    )

    skale_config = FairSkaleConfig(schain_info=schain_info, node_info=current_node_info)

    return FairConfig(
        seal_engine=base_config.config['sealEngine'],
        params={**base_config.config['params'], **dynamic_params},
        unddos=base_config.config['unddos'],
        genesis=base_config.config['genesis'],
        accounts=accounts,
        skale_config=skale_config,
    )
