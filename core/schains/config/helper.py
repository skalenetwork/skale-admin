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
import os
from typing import Dict, List

from web3 import Web3
from Crypto.Hash import keccak

from skale.dataclasses.skaled_ports import SkaledPorts

from core.schains.ssl import get_ssl_filepath
from core.schains.config.directory import schain_config_filepath
from tools.configs.containers import (
    DATA_DIR_CONTAINER_PATH,
    SHARED_SPACE_CONTAINER_PATH
)
from tools.configs.ima import IMA_ENDPOINT

from core.schains.dkg.utils import get_secret_key_share_filepath
from tools.helper import read_json

from tools.configs import SGX_SERVER_URL
from tools.configs.schains import STATIC_SCHAIN_PARAMS_FILEPATH
from tools.configs.containers import LOCAL_IP


logger = logging.getLogger(__name__)


def get_static_schain_params():
    return read_json(STATIC_SCHAIN_PARAMS_FILEPATH)


def get_context_contract():
    return get_static_schain_params()['context_contract']


def fix_address(address):
    return Web3.toChecksumAddress(address)


def get_chain_id(schain_name):
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(schain_name.encode("utf-8"))
    hash_ = keccak_hash.hexdigest()
    hash_ = hash_[:13]			# use 52 bits
    return "0x" + hash_


def _string_to_storage(slot: int, string: str) -> dict:
    # https://solidity.readthedocs.io/en/develop/miscellaneous.html#bytes-and-string
    storage = dict()
    binary = string.encode()
    length = len(binary)
    if length < 32:
        binary += (2 * length).to_bytes(32 - length, 'big')
        storage[hex(slot)] = '0x' + binary.hex()
    else:
        storage[hex(slot)] = hex(2 * length + 1)

        keccak_hash = keccak.new(digest_bits=256)
        keccak_hash.update(slot.to_bytes(32, 'big'))
        offset = int.from_bytes(keccak_hash.digest(), 'big')

        def chunks(size, source):
            for i in range(0, len(source), size):
                yield source[i:i + size]

        for index, data in enumerate(chunks(32, binary)):
            if len(data) < 32:
                data += int(0).to_bytes(32 - len(data), 'big')
            storage[hex(offset + index)] = '0x' + data.hex()
    return storage


def get_node_ips_from_config(config: Dict) -> List[str]:
    if config is None:
        return []
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']
    return [
        node_data['ip']
        for node_data in schain_nodes_config
    ]


def get_base_port_from_config(config: Dict) -> int:
    return config['skaleConfig']['nodeInfo']['basePort']


def get_own_ip_from_config(config: Dict) -> str:
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']
    own_id = config['skaleConfig']['nodeInfo']['nodeID']
    for node_data in schain_nodes_config:
        if node_data['nodeID'] == own_id:
            return node_data['ip']
    return None


def get_schain_ports(schain_name):
    config = get_schain_config(schain_name)
    return get_schain_ports_from_config(config)


def get_schain_ports_from_config(config):
    if config is None:
        return {}
    node_info = config["skaleConfig"]["nodeInfo"]
    return {
        'http': int(node_info["httpRpcPort"]),
        'ws': int(node_info["wsRpcPort"]),
        'https': int(node_info["httpsRpcPort"]),
        'wss': int(node_info["wssRpcPort"]),
        'info_http': int(node_info["infoHttpRpcPort"])
    }


def get_skaled_http_address(schain_name: str) -> str:
    config = get_schain_config(schain_name)
    return get_skaled_http_address_from_config(config)


def get_skaled_http_address_from_config(config: Dict) -> str:
    node = config['skaleConfig']['nodeInfo']
    return 'http://{}:{}'.format(
        LOCAL_IP,
        node['basePort'] + SkaledPorts.HTTP_JSON.value
    )


def get_schain_config(schain_name):
    config_filepath = schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        return None
    with open(config_filepath) as f:
        schain_config = json.load(f)
    return schain_config


def get_schain_env(ulimit_check=True):
    env = {'SEGFAULT_SIGNALS': 'all'}
    if not ulimit_check:
        env.update({
            'NO_ULIMIT_CHECK': 1
        })
    return env


def get_schain_container_cmd(schain_name: str,
                             public_key: str = None,
                             start_ts: int = None,
                             enable_ssl: bool = True) -> str:
    opts = get_schain_container_base_opts(schain_name, enable_ssl=enable_ssl)
    if public_key and str(start_ts):
        sync_opts = get_schain_container_sync_opts(public_key, start_ts)
        opts.extend(sync_opts)
    return ' '.join(opts)


def get_schain_container_sync_opts(public_key: str,
                                   start_ts: int) -> list:
    return [
        '--download-snapshot readfromconfig',  # tmp, parameter is needed, but value is not used
        f'--public-key {public_key}',
        f'--start-timestamp {start_ts}'
    ]


def get_schain_container_base_opts(schain_name: str,
                                   enable_ssl: bool = True) -> list:
    config_filepath = schain_config_filepath(schain_name, in_schain_container=True)
    ssl_key, ssl_cert = get_ssl_filepath()
    ports = get_schain_ports(schain_name)

    static_schain_params = get_static_schain_params()
    static_schain_cmd = static_schain_params.get('schain_cmd', None)
    cmd = [
        f'--config {config_filepath}',
        f'-d {DATA_DIR_CONTAINER_PATH}',
        f'--ipcpath {DATA_DIR_CONTAINER_PATH}',
        f'--http-port {ports["http"]}',
        f'--https-port {ports["https"]}',
        f'--ws-port {ports["ws"]}',
        f'--wss-port {ports["wss"]}',
        f'--sgx-url {SGX_SERVER_URL}',
        f'--shared-space-path {SHARED_SPACE_CONTAINER_PATH}/data',
        f'--main-net-url {IMA_ENDPOINT}'
    ]

    if static_schain_cmd:
        cmd.extend(static_schain_cmd)

    if enable_ssl:
        cmd.extend([
            f'--ssl-key {ssl_key}',
            f'--ssl-cert {ssl_cert}'
        ])
    return cmd


def get_schain_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpRpcPort"]), int(node_info["wsRpcPort"])


def get_local_schain_http_endpoint(name):
    http_port, _ = get_schain_rpc_ports(name)
    return f'http://0.0.0.0:{http_port}'


def get_schain_ssl_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpsRpcPort"]), int(node_info["wssRpcPort"])


def parse_public_key_info(bls_public_key):
    public_key_list = bls_public_key.split(':')
    return {
        'blsPublicKey0': str(public_key_list[0]),
        'blsPublicKey1': str(public_key_list[1]),
        'blsPublicKey2': str(public_key_list[2]),
        'blsPublicKey3': str(public_key_list[3])
    }


def get_bls_public_keys(schain_name, rotation_id):
    key_file = get_secret_key_share_filepath(schain_name, rotation_id)
    data = read_json(key_file)
    return data["bls_public_keys"]
