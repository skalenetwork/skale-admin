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
from skale.dataclasses.skaled_ports import SkaledPorts
from skale.schain_config.ports_allocation import get_schain_base_port_on_node

from core.schains.config.skale_manager_opts import SkaleManagerOpts
from tools.configs import SGX_SSL_KEY_FILEPATH, SGX_SSL_CERT_FILEPATH
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH, SCHAIN_IMA_ABI_FILEPATH

from core.schains.dkg.utils import get_secret_key_share_filepath
from tools.helper import read_json


logger = logging.getLogger(__name__)


@dataclass
class CurrentNodeInfo(NodeInfo):
    """Dataclass that represents nodeInfo key of the skaleConfig section"""
    ima_message_proxy_schain: str
    ima_message_proxy_mainnet: str
    ecdsa_key_name: str
    wallets: dict

    skale_manager_opts: SkaleManagerOpts
    static_node_info: dict

    sync_node: bool
    archive: bool
    catchup: bool

    pg_threads: int
    pg_threads_limit: int

    def to_dict(self):
        """Returns camel-case representation of the CurrentNodeInfo object"""
        node_info = {
            **super().to_dict(),
            **{
                'imaMessageProxySChain': self.ima_message_proxy_schain,
                'imaMessageProxyMainNet': self.ima_message_proxy_mainnet,
                'ecdsaKeyName': self.ecdsa_key_name,
                'wallets': self.wallets,
                'imaMonitoringPort': self.base_port + SkaledPorts.IMA_MONITORING.value,
                'skale-manager': self.skale_manager_opts.to_dict(),
                'syncNode': self.sync_node,
                'info-acceptors': 1,
                **self.static_node_info
            }
        }
        if self.archive is not None and self.sync_node:
            node_info['archiveMode'] = self.archive
        if self.catchup is not None and self.sync_node:
            node_info['syncFromCatchup'] = self.catchup
        return node_info


def generate_current_node_info(
    node: dict, node_id: int, ecdsa_key_name: str, static_node_info: dict,
    schain: dict, schains_on_node: list, rotation_id: int, skale_manager_opts: SkaleManagerOpts,
    sync_node: bool = False, archive: bool = False, catchup: bool = False
) -> CurrentNodeInfo:
    schain_base_port_on_node = get_schain_base_port_on_node(
        schains_on_node,
        schain['name'],
        node['port']
    )

    wallets = {} if sync_node else generate_wallets_config(schain['name'], rotation_id)

    if ecdsa_key_name is None:
        logger.warning(f'Generating CurrentNodeInfo for {schain["name"]}, ecdsa_key_name is None')
        ecdsa_key_name = ""

    return CurrentNodeInfo(
        node_id=node_id,
        name=node['name'],
        base_port=schain_base_port_on_node,
        ecdsa_key_name=ecdsa_key_name,
        wallets=wallets,
        skale_manager_opts=skale_manager_opts,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
        **get_message_proxy_addresses()
    )


def generate_wallets_config(schain_name: str, rotation_id: int) -> dict:
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
    secret_key_share_config = read_json(secret_key_share_filepath)

    wallets = {
        'ima': {
            'keyShareName': secret_key_share_config['key_share_name'],
            't': secret_key_share_config['t'],
            'n': secret_key_share_config['n'],
            'certFile': SGX_SSL_CERT_FILEPATH,
            'keyFile': SGX_SSL_KEY_FILEPATH
        }
    }
    common_public_keys = secret_key_share_config['common_public_key']
    for (i, value) in enumerate(common_public_keys):
        name = 'commonBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    public_keys = secret_key_share_config['public_key']
    for (i, value) in enumerate(public_keys):
        name = 'BLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    return wallets


def get_message_proxy_addresses():
    mainnet_ima_abi = read_json(MAINNET_IMA_ABI_FILEPATH)
    schain_ima_abi = read_json(SCHAIN_IMA_ABI_FILEPATH)
    ima_mp_schain = schain_ima_abi['message_proxy_chain_address']
    ima_mp_mainnet = mainnet_ima_abi['message_proxy_mainnet_address']
    return {
        'ima_message_proxy_schain': ima_mp_schain,
        'ima_message_proxy_mainnet': ima_mp_mainnet
    }
