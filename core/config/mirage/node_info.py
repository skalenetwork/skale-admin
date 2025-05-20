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

from core.schains.dkg.utils import get_secret_key_share_filepath
from core.config.schain.static_params import get_static_chain_name_mirage

from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH
from tools.helper import read_json


logger = logging.getLogger(__name__)


@dataclass
class MirageCurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of Mirage the skaleConfig section"""

    ecdsa_key_name: str
    wallets: dict

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
                'wallets': self.wallets,
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
    nodes_in_chain: int,
    port: Port,
    common_bls_public_keys: list[str],
    sync_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
) -> MirageCurrentNodeInfo:
    wallets = generate_mirage_wallets_config(
        group_index, sync_node, nodes_in_chain, common_bls_public_keys
    )

    if ecdsa_key_name is None:
        ecdsa_key_name = ''

    return MirageCurrentNodeInfo(
        node_id=node_id,
        name=str(node_id),
        base_port=port,
        ecdsa_key_name=ecdsa_key_name,
        wallets=wallets,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
    )


def generate_mirage_wallets_config(
    group_index: int,
    sync_node: bool,
    nodes_in_chain: int,
    common_bls_public_keys: list[str],
) -> dict:
    wallets = {'ima': {}}
    formatted_common_pk = {}

    for i, value in enumerate(common_bls_public_keys):
        name = 'commonBLSPublicKey' + str(i)
        formatted_common_pk[name] = str(value)

    wallets['ima'].update({'n': nodes_in_chain, **formatted_common_pk})

    if not sync_node:
        secret_key_share_filepath = get_secret_key_share_filepath(
            get_static_chain_name_mirage(), group_index
        )
        secret_key_share_config = read_json(secret_key_share_filepath)

        wallets['ima'].update(
            {
                'keyShareName': secret_key_share_config['key_share_name'],
                't': secret_key_share_config['t'],
                'certFile': SGX_SSL_CERT_FILEPATH,
                'keyFile': SGX_SSL_KEY_FILEPATH,
            }
        )

        public_keys = secret_key_share_config['public_key']
        for i, value in enumerate(public_keys):
            name = 'BLSPublicKey' + str(i)
            wallets['ima'][name] = str(value)

    return wallets
