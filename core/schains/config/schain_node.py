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
from skale.dataclasses.node_info import NodeInfo
from skale.schain_config.ports_allocation import get_schain_base_port_on_node
from skale.utils.helper import ip_from_bytes
from skale.utils.web3_utils import public_key_to_address

from core.schains.config.helper import compose_public_key_info, get_bls_public_keys


@dataclass
class SChainNodeInfo(NodeInfo):
    """Dataclass that represents sChain node key of the schain section"""
    public_key: str
    bls_public_key: list
    owner: str
    schain_index: int
    ip: str
    public_ip: str

    def to_dict(self):
        """ Returns camel-case representation of the SChainNodeInfo object """
        return {
            **super().to_dict(),
            **compose_public_key_info(self.bls_public_key),
            **{
                'publicKey': self.public_key,
                'owner': self.owner,
                'schainIndex': self.schain_index,
                'ip': self.ip,
                'publicIP': self.public_ip
            }
        }


def generate_schain_nodes(schain_nodes_with_schains: list, schain_name, rotation_id: int):
    schain_nodes = []
    bls_public_keys = get_bls_public_keys(schain_name, rotation_id)
    for i, node in enumerate(schain_nodes_with_schains, 1):
        base_port = get_schain_base_port_on_node(node['schains'], schain_name, node['port'])
        node_info = SChainNodeInfo(
            name=node['name'],
            node_id=node['id'],
            base_port=base_port,
            bls_public_key=bls_public_keys[i],
            schain_index=i,
            ip=ip_from_bytes(node['ip']),
            public_key=node['publicKey'],
            public_ip=ip_from_bytes(node['publicIP']),
            owner=public_key_to_address(node['publicKey'])
        ).to_dict()
        schain_nodes.append(node_info)

    return schain_nodes
