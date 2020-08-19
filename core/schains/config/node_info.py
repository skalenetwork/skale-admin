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

from core.schains.config.ima import get_message_proxy_addresses
from core.schains.volume import get_allocation_option_name
from tools.configs import SGX_SERVER_URL
from tools.configs.ima import IMA_ENDPOINT

from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.helper import read_json


@dataclass
class CurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of the skaleConfig section"""
    bind_ip: str
    log_level: str
    log_level_config: str
    ima_mainnet: str
    ima_message_proxy_schain: str
    ima_message_proxy_mainnet: str
    rotate_after_block: int
    ecdsa_key_name: str
    wallets: dict

    min_cache_size: int
    max_cache_size: int
    collection_queue_size: int
    collection_duration: int
    transaction_queue_size: int
    max_open_leveldb_files: int

    def to_dict(self):
        """Returns camel-case representation of the CurrentNodeInfo object"""
        return {
            **super().to_dict(),
            **{
                'bindIP': self.bind_ip,
                'logLevel': self.log_level,
                'logLevelConfig': self.log_level_config,
                'imaMainNet': self.ima_mainnet,
                'imaMessageProxySChain': self.ima_message_proxy_schain,
                'imaMessageProxyMainNet': self.ima_message_proxy_mainnet,
                'rotateAfterBlock': self.rotate_after_block,
                'ecdsaKeyName': self.ecdsa_key_name,
                'wallets': self.wallets,
                'minCacheSize': self.min_cache_size,
                'maxCacheSize': self.max_cache_size,
                'collectionQueueSize': self.collection_queue_size,
                'collectionDuration': self.collection_duration,
                'transactionQueueSize': self.transaction_queue_size,
                'maxOpenLeveldbFiles': self.max_open_leveldb_files,
            }
        }


def generate_current_node_info(node: dict, node_id: int, ecdsa_key_name: str,
                               static_schain_params: dict, schain: dict,
                               schains_on_node: list, rotation_id: int) -> CurrentNodeInfo:
    schain_base_port_on_node = get_schain_base_port_on_node(schains_on_node, schain['name'],
                                                            node['port'])
    schain_size_name = get_allocation_option_name(schain)
    return CurrentNodeInfo(
        node_id=node_id,
        name=node['name'],
        base_port=schain_base_port_on_node,
        ima_mainnet=IMA_ENDPOINT,
        ecdsa_key_name=ecdsa_key_name,
        wallets=generate_wallets_config(schain['name'], rotation_id),
        **get_message_proxy_addresses(),
        **static_schain_params['current_node_info'],
        **static_schain_params['cache_options'][schain_size_name]
    )


def generate_wallets_config(schain_name, rotation_id):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    secret_key_share_config = read_json(secret_key_share_filepath)
    wallets = {
        'ima': {
            'url': SGX_SERVER_URL,
            'keyShareName': secret_key_share_config['key_share_name'],
            't': secret_key_share_config['t'],
            'n': secret_key_share_config['n']
        }
    }
    common_public_keys = secret_key_share_config['common_public_key']
    for (i, value) in enumerate(common_public_keys):
        name = 'insecureCommonBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    public_keys = secret_key_share_config['public_key']
    for (i, value) in enumerate(public_keys):
        name = 'insecureBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    return wallets
