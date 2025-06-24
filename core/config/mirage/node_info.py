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

from skale.types.node import NodeId, Port
from skale.dataclasses.node_info import NodeInfo


logger = logging.getLogger(__name__)


@dataclass
class MirageCurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of Mirage the skaleConfig section"""

    ecdsa_key_name: str
    static_node_info: dict
    sync_node: bool
    catchup: bool
    archive: bool

    def to_dict(self):
        """Returns camel-case representation of the MirageCurrentNodeInfo object"""
        node_info = {
            **super().to_dict(),
            **{
                'ecdsaKeyName': self.ecdsa_key_name,
                'syncNode': self.sync_node,
                'info-acceptors': 1,
                **self.static_node_info,
            },
        }
        if self.sync_node:
            node_info['archiveMode'] = self.archive
            node_info['syncFromCatchup'] = self.catchup
        return node_info


def generate_mirage_current_node_info(
    node_id: NodeId,
    ecdsa_key_name: str,
    static_node_info: dict,
    group_index: int,
    port: Port,
    common_bls_public_keys: list[str],
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
) -> MirageCurrentNodeInfo:
    if ecdsa_key_name is None:
        ecdsa_key_name = ''

    return MirageCurrentNodeInfo(
        node_id=node_id,
        name=str(node_id),
        base_port=port,
        ecdsa_key_name=ecdsa_key_name,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
    )

