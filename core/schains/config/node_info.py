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
        if self.sync_node:
            node_info['archiveMode'] = self.archive
            node_info['syncFromCatchup'] = self.catchup
        return node_info


def generate_current_node_info(
    node: dict, node_id: int, ecdsa_key_name: str, static_node_info: dict,
    schain: dict, rotation_id: int,
    nodes_in_schain: int,
    skale_manager_opts: SkaleManagerOpts,
    schain_base_port: int,
    common_bls_public_keys: list[str],
    sync_node: bool = False, archive: bool = False, catchup: bool = False
) -> CurrentNodeInfo:
    wallets = generate_wallets_config(
        schain['name'],
        rotation_id,
        sync_node,
        nodes_in_schain,
        common_bls_public_keys
    )

    if ecdsa_key_name is None:
        ecdsa_key_name = ''

    return CurrentNodeInfo(
        node_id=node_id,
        name=node['name'],
        base_port=schain_base_port,
        ecdsa_key_name=ecdsa_key_name,
        wallets=wallets,
        skale_manager_opts=skale_manager_opts,
        sync_node=sync_node,
        archive=archive,
        catchup=catchup,
        static_node_info=static_node_info,
        **get_message_proxy_addresses()
    )


def generate_wallets_config(
    schain_name: str,
    rotation_id: int,
    sync_node: bool,
    nodes_in_schain: int,
    common_bls_public_keys: str
) -> dict:
    wallets = {'ima': {}}
    formatted_common_pk = {}

    for (i, value) in enumerate(common_bls_public_keys):
        name = 'commonBLSPublicKey' + str(i)
        formatted_common_pk[name] = str(value)

    wallets['ima'].update({
        'n': nodes_in_schain,
        **formatted_common_pk
    })

    if not sync_node:
        secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
        secret_key_share_config = read_json(secret_key_share_filepath)

        wallets['ima'].update({
            'keyShareName': secret_key_share_config['key_share_name'],
            't': secret_key_share_config['t'],
            'certFile': SGX_SSL_CERT_FILEPATH,
            'keyFile': SGX_SSL_KEY_FILEPATH,
        })

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
