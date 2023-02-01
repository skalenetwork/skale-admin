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
from core.schains.config.helper import get_patches, get_static_schain_params
from core.schains.config.skale_manager_opts import SkaleManagerOpts


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
    node: dict, ecdsa_key_name: str, schains_on_node: list, schain_nodes_with_schains: list,
    rotation_id: int, node_groups: dict, skale_manager_opts: SkaleManagerOpts,
    sync_node: bool = False, archive=None, catchup=None
) -> SkaleConfig:
    static_schain_params = get_static_schain_params()
    patches = get_patches()

    contract_settings = generate_contract_settings(
        on_chain_owner=on_chain_owner,
        schain_nodes=schain_nodes_with_schains
    )

    node_info = generate_current_node_info(
        node_id=node_id,
        node=node,
        ecdsa_key_name=ecdsa_key_name,
        static_schain_params=static_schain_params,
        schain=schain,
        schains_on_node=schains_on_node,
        rotation_id=rotation_id,
        skale_manager_opts=skale_manager_opts,
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
        static_schain_params=static_schain_params,
        nodes=schain_nodes,
        node_groups=node_groups,
        patches=patches
    )

    return SkaleConfig(
        contract_settings=contract_settings,
        node_info=node_info,
        schain_info=schain_info,
    )
