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

from eth_typing import HexStr
from dataclasses import dataclass
from skale.dataclasses.node_info import NodeInfo
from skale.utils.helper import ip_from_bytes
from skale.types.node import MirageNode

from core.config.schain.helper import parse_public_key_info, get_bls_public_keys
from core.config.schain.static_params import get_mirage_chain_name


@dataclass
class MirageChainNodeInfo(NodeInfo):
    bls_public_key: str
    owner: str
    committee_index: int
    ip: str
    public_key: HexStr

    def to_dict(self):
        node_info = super().to_dict()
        return {
            **node_info,
            **parse_public_key_info(self.bls_public_key),
            **{
                'owner': self.owner,
                'schainIndex': self.committee_index,
                'ip': self.ip,
                'publicKey': self.public_key,
            },
        }


def generate_mirage_chain_nodes(
    committee_nodes: list[MirageNode], committee_id: int, is_committee_node: bool
) -> list[MirageChainNodeInfo]:
    chain_nodes = []

    if is_committee_node:
        bls_public_keys = get_bls_public_keys(get_mirage_chain_name(), committee_id)
    else:
        bls_public_keys = ['0:0:1:0'] * len(committee_nodes)

    for i, node in enumerate(committee_nodes, 1):
        node_info = MirageChainNodeInfo(
            name=node.name,
            node_id=node.id,
            base_port=node.port,
            bls_public_key=bls_public_keys[i - 1],
            committee_index=i,
            ip=ip_from_bytes(node.ip),
            owner=node.address,
            public_key=node.public_key,
        )
        chain_nodes.append(node_info)

    return chain_nodes
