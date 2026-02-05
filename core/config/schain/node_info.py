#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019-Present SKALE Labs
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
from skale.types.node import Node, NodeId, Port
from skale.types.schain import SchainStructure

from core.dkg.utils import get_secret_key_share_filepath
from tools.configs.sgx import SGX_SSL_CERT_FILEPATH, SGX_SSL_KEY_FILEPATH
from tools.helper import read_json

logger = logging.getLogger(__name__)


@dataclass
class CurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of the skaleConfig section"""

    ecdsa_key_name: str
    wallets: dict

    static_node_info: dict

    passive_node: bool
    catchup: bool
    archive: bool

    min_gas_price: int | None = None
    max_gas_price: int | None = None

    def to_dict(self):
        """Returns camel-case representation of the CurrentNodeInfo object"""
        node_info = {
            **super().to_dict(),
            **{
                'ecdsaKeyName': self.ecdsa_key_name,
                'wallets': self.wallets,
                'syncNode': self.passive_node,
                'info-acceptors': 1,
                **self.static_node_info,
            },
        }

        if self.min_gas_price is not None:
            min_price = self.min_gas_price
            node_info['dynamicPricingMinPrice'] = min_price
            node_info['dynamicPricingStartPrice'] = min_price

        if self.max_gas_price is not None:
            node_info['dynamicPricingMaxPrice'] = self.max_gas_price

        if self.passive_node:
            node_info['archiveMode'] = self.archive
            node_info['syncFromCatchup'] = self.catchup
        return node_info


def generate_current_node_info(
    node: Node,
    node_id: NodeId,
    ecdsa_key_name: str,
    static_node_info: dict,
    schain: SchainStructure,
    rotation_id: int,
    nodes_in_schain: int,
    schain_base_port: Port,
    common_bls_public_keys: list[str],
    passive_node: bool = False,
    archive: bool = False,
    catchup: bool = False,
) -> CurrentNodeInfo:
    wallets = generate_wallets_config(
        schain.name, rotation_id, passive_node, nodes_in_schain, common_bls_public_keys
    )

    if ecdsa_key_name is None:
        ecdsa_key_name = ''

    return CurrentNodeInfo(
        node_id=node_id,
        name=node['name'],
        base_port=schain_base_port,
        ecdsa_key_name=ecdsa_key_name,
        wallets=wallets,
        passive_node=passive_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
        min_gas_price=schain.options.min_gas_price,
        max_gas_price=schain.options.max_gas_price,
    )


def generate_wallets_config(
    schain_name: str,
    rotation_id: int,
    passive_node: bool,
    nodes_in_schain: int,
    common_bls_public_keys: list[str],
) -> dict:
    wallets = {'ima': {}}
    formatted_common_pk = {}

    for i, value in enumerate(common_bls_public_keys):
        name = 'commonBLSPublicKey' + str(i)
        formatted_common_pk[name] = str(value)

    wallets['ima'].update({'n': nodes_in_schain, **formatted_common_pk})

    if not passive_node:
        secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
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
