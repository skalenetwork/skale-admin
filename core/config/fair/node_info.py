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

from skale.dataclasses.node_info import NodeInfo
from skale.types.node import NodeId, Port

logger = logging.getLogger(__name__)


@dataclass
class FairCurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of Fair the skaleConfig section"""

    ecdsa_key_name: str
    static_node_info: dict
    is_committee_node: bool
    catchup: bool
    archive: bool

    def to_dict(self):
        """Returns camel-case representation of the FairCurrentNodeInfo object"""
        node_info = {
            **super().to_dict(),
            **{
                'ecdsaKeyName': self.ecdsa_key_name,
                # 'syncNode': not self.is_committee_node,
                'info-acceptors': 1,
                **self.static_node_info,
            },
        }
        # todod: handle later
        # if not self.is_committee_node:
        #     node_info['archiveMode'] = self.archive
        #     node_info['syncFromCatchup'] = self.catchup
        return node_info


def generate_fair_current_node_info(
    node_id: NodeId,
    ecdsa_key_name: str,
    static_node_info: dict,
    port: Port,
    is_committee_node: bool,
    archive: bool = False,
    catchup: bool = False,
) -> FairCurrentNodeInfo:
    if ecdsa_key_name is None:
        ecdsa_key_name = ''

    return FairCurrentNodeInfo(
        node_id=node_id,
        name=str(node_id),
        base_port=port,
        ecdsa_key_name=ecdsa_key_name,
        is_committee_node=is_committee_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
    )
