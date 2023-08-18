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

import logging
from typing import Dict, List, Optional, Tuple

from Crypto.Hash import keccak
from web3 import Web3

from core.schains.dkg.utils import get_secret_key_share_filepath
from tools.helper import read_json
from tools.configs import STATIC_PARAMS_FILEPATH, ENV_TYPE
from tools.helper import safe_load_yml


logger = logging.getLogger(__name__)


def get_static_params(env_type=ENV_TYPE, path=STATIC_PARAMS_FILEPATH):
    ydata = safe_load_yml(path)
    return ydata['envs'][env_type]


def fix_address(address):
    return Web3.to_checksum_address(address)


def get_chain_id(schain_name: str) -> str:
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(schain_name.encode("utf-8"))
    hash_ = keccak_hash.hexdigest()
    hash_ = hash_[:13]			# use 52 bits
    return "0x" + hash_


def get_schain_id(schain_name: str) -> int:
    return int(get_chain_id(schain_name), 16)


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


def get_own_ip_from_config(config: Dict) -> Optional[str]:
    schain_nodes_config = config['skaleConfig']['sChain']['nodes']
    own_id = config['skaleConfig']['nodeInfo']['nodeID']
    for node_data in schain_nodes_config:
        if node_data['nodeID'] == own_id:
            return node_data['ip']
    return None


def get_schain_ports_from_config(config: Dict):
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


def get_schain_env(ulimit_check=True):
    env = {'SEGFAULT_SIGNALS': 'all'}
    if not ulimit_check:
        env.update({
            'NO_ULIMIT_CHECK': 1
        })
    return env


def get_schain_rpc_ports_from_config(config: Dict) -> Tuple[int, int]:
    node_info = config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpRpcPort"]), int(node_info["wsRpcPort"])


def get_local_schain_http_endpoint_from_config(config: Dict) -> str:
    http_port, _ = get_schain_rpc_ports_from_config(config)
    return f'http://127.0.0.1:{http_port}'


def get_schain_ssl_rpc_ports_from_config(config: Dict) -> Tuple[int, int]:
    node_info = config["skaleConfig"]["nodeInfo"]
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
