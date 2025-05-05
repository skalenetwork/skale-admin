#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025-Present SKALE Labs
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
from skale.dataclasses.node_info import NodeInfo
from skale.schain_config.ports_allocation import get_schain_base_port_on_node
from skale.utils.helper import ip_from_bytes
from skale.utils.web3_utils import public_key_to_address

from core.config.schain.helper import parse_public_key_info, get_bls_public_keys


@dataclass
class MirageSChainNodeInfo(NodeInfo):
    """Dataclass that represents Mirage sChain node key of the schain section"""

    bls_public_key: str
    owner: str
    schain_index: int
    ip: str

    def to_dict(self):
        """Returns camel-case representation of the MirageSChainNodeInfo object"""
        node_info = super().to_dict()
        # dropping infoHttpRpcPort since skaled doesn't support this key in nodes section
        node_info.pop('infoHttpRpcPort', None)
        return {
            **node_info,
            **parse_public_key_info(self.bls_public_key),
            **{
                'owner': self.owner,
                'schainIndex': self.schain_index,
                'ip': self.ip,
            },
        }


def generate_mirage_schain_nodes(
    schain_nodes_with_schains: list, schain_name: str, rotation_id: int, sync_node: bool = False
) -> list[MirageSChainNodeInfo]:
    schain_nodes = []

    if sync_node:
        bls_public_keys = ['0:0:1:0'] * len(schain_nodes_with_schains)
    else:
        bls_public_keys = get_bls_public_keys(schain_name, rotation_id)

    for i, node in enumerate(schain_nodes_with_schains, 1):
        base_port = get_schain_base_port_on_node(node['schains'], schain_name, node['port'])
        node_info = MirageSChainNodeInfo(
            name=node['name'],
            node_id=node['id'],
            base_port=base_port,
            bls_public_key=bls_public_keys[i - 1],
            schain_index=i,
            ip=ip_from_bytes(node['ip']),
            owner=public_key_to_address(node['publicKey']),
        ).to_dict()
        schain_nodes.append(node_info)

    return schain_nodes
