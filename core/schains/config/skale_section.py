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

from core.schains.config.contract_settings import (
    ContractSettings, generate_contract_settings
)
from core.schains.config.node_info import CurrentNodeInfo, generate_current_node_info
from core.schains.config.schain_info import SChainInfo, generate_schain_info
from core.schains.config.schain_node import generate_schain_nodes
from core.schains.config.skale_manager_opts import SkaleManagerOpts
from core.schains.config.static_params import get_static_schain_info, get_static_node_info
from core.schains.limits import get_schain_type


@dataclass
class SkaleConfig:
    """Dataclass that represents skaleConfig key of the sChain config"""
    contract_settings: ContractSettings
    node_info: CurrentNodeInfo
    schain_info: SChainInfo

    def to_dict(self):
        """Returns camel-case representation of the SkaleConfig object"""
        return {
            'contractSettings': self.contract_settings.to_dict(),
            'nodeInfo': self.node_info.to_dict(),
            'sChain': self.schain_info.to_dict(),
        }


def generate_skale_section(
    schain: dict, on_chain_etherbase: str, on_chain_owner: str, schain_id: int, node_id: int,
    node: dict, ecdsa_key_name: str, schain_nodes_with_schains: list,
    rotation_id: int, node_groups: dict, skale_manager_opts: SkaleManagerOpts,
    schain_base_port: int,
    common_bls_public_keys: list[str], sync_node: bool = False, archive=None, catchup=None
) -> SkaleConfig:
    contract_settings = generate_contract_settings(
        on_chain_owner=on_chain_owner,
        schain_nodes=schain_nodes_with_schains
    )

    schain_type = get_schain_type(schain['partOfNode'])
    static_node_info = get_static_node_info(schain_type)
    static_schain_info = get_static_schain_info()
    nodes_in_schain = len(schain_nodes_with_schains)

    node_info = generate_current_node_info(
        node_id=node_id,
        node=node,
        ecdsa_key_name=ecdsa_key_name,
        static_node_info=static_node_info,
        schain=schain,
        rotation_id=rotation_id,
        skale_manager_opts=skale_manager_opts,
        schain_base_port=schain_base_port,
        nodes_in_schain=nodes_in_schain,
        common_bls_public_keys=common_bls_public_keys,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup
    )

    schain_nodes = generate_schain_nodes(
        schain_nodes_with_schains=schain_nodes_with_schains,
        schain_name=schain['name'],
        rotation_id=rotation_id,
        sync_node=sync_node
    )

    schain_info = generate_schain_info(
        schain_id=schain_id,
        schain=schain,
        on_chain_etherbase=on_chain_etherbase,
        static_schain_info=static_schain_info,
        nodes=schain_nodes,
        node_groups=node_groups
    )

    return SkaleConfig(
        contract_settings=contract_settings,
        node_info=node_info,
        schain_info=schain_info,
    )
