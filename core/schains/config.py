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

import json
import logging

from skale.schain_config.generator import generate_skale_schain_config

from core.schains.ssl import get_ssl_filepath
from core.schains.helper import read_base_config, get_schain_config_filepath
from tools.sgx_utils import SGX_SERVER_URL
from tools.configs.containers import DATA_DIR_CONTAINER_PATH

from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.helper import read_json
from tools.configs.ima import IMA_ENDPOINT, MAINNET_PROXY_PATH

logger = logging.getLogger(__name__)


def generate_schain_config(skale, schain_name, node_id):
    base_config = read_base_config()
    wallets = generate_wallets_config(schain_name)
    ima_mainnet_url = IMA_ENDPOINT
    ima_mp_schain, ima_mp_mainnet = get_mp_addresses()
    return generate_skale_schain_config(
        skale=skale,
        schain_name=schain_name,
        node_id=node_id,
        base_config=base_config,
        ima_mainnet=ima_mainnet_url,
        ima_mp_schain=ima_mp_schain,
        ima_mp_mainnet=ima_mp_mainnet,
        wallets=wallets
    )


def get_mp_addresses():
    ima_abi = read_json(MAINNET_PROXY_PATH)
    ima_mp_schain = None  # todo: unknown at the launch time, tbd
    ima_mp_mainnet = ima_abi['message_proxy_mainnet_address']
    return ima_mp_schain, ima_mp_mainnet


def generate_wallets_config(schain_name):
    secret_key_share_filepath = get_secret_key_share_filepath(schain_name)
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
        name = 'insecureBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    public_keys = secret_key_share_config['public_key']
    for (i, value) in enumerate(public_keys):
        name = 'insecureCommonBLSPublicKey' + str(i)
        wallets['ima'][name] = str(value)

    return wallets


def save_schain_config(schain_config, schain_name):
    schain_config_filepath = get_schain_config_filepath(schain_name)
    with open(schain_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)

    return schain_config_filepath


def get_schain_ports(schain_name):
    schain_config = get_schain_config(schain_name)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return {
        'http': int(node_info["httpRpcPort"]),
        'ws': int(node_info["wsRpcPort"]),
        'https': int(node_info["httpsRpcPort"]),
        'wss': int(node_info["wssRpcPort"])
    }


def get_schain_config(schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    with open(config_filepath) as f:
        schain_config = json.load(f)
    return schain_config


def get_schain_env(schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    ssl_key, ssl_cert = get_ssl_filepath()
    ports = get_schain_ports(schain_name)
    return {
        "SSL_KEY_PATH": ssl_key,
        "SSL_CERT_PATH": ssl_cert,
        "HTTP_RPC_PORT": ports['http'],
        "HTTPS_RPC_PORT": ports['https'],
        "WS_RPC_PORT": ports['ws'],
        "WSS_RPC_PORT": ports['wss'],

        "SCHAIN_ID": schain_name,
        "CONFIG_FILE": config_filepath,
        "DATA_DIR": DATA_DIR_CONTAINER_PATH
    }
