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
from typing import Dict, List, Optional

from Crypto.Hash import keccak
from web3 import Web3

from core.config.fair.helper import get_current_nodes as get_fair_current_nodes
from core.dkg.utils import get_secret_key_share_filepath
from core.types.settings import EnvType
from tools.constants import FAIR_STATIC_PARAMS_FILEPATH, STATIC_PARAMS_FILEPATH
from tools.helper import is_fair, read_json, safe_load_yml

logger = logging.getLogger(__name__)


def get_static_params(env_type: EnvType, path=STATIC_PARAMS_FILEPATH):
    ydata = safe_load_yml(path)
    return ydata['envs'][env_type]


def get_static_params_fair(env_type: EnvType, path=FAIR_STATIC_PARAMS_FILEPATH):
    ydata = safe_load_yml(path)
    return ydata['envs'][env_type]


def fix_address(address):
    return Web3.to_checksum_address(address)


def get_chain_id(schain_name: str) -> str:
    keccak_hash = keccak.new(digest_bits=256)
    keccak_hash.update(schain_name.encode('utf-8'))
    hash_ = keccak_hash.hexdigest()
    hash_ = hash_[:13]  # use 52 bits
    return '0x' + hash_


def get_schain_id(schain_name: str) -> int:
    return int(get_chain_id(schain_name), 16)


def get_schain_current_nodes(config: Dict) -> List[dict]:
    return config['skaleConfig']['sChain']['nodes']


def get_node_ips_from_config(config: Dict) -> List[str]:
    if is_fair():
        group_data = get_fair_current_nodes(config)
    else:
        group_data = get_schain_current_nodes(config)
    if len(group_data) == 0:
        return []
    return [node_data['ip'] for node_data in group_data]


def get_base_port_from_config(config: Dict | None) -> int:
    if config is None:
        return 0
    return config['skaleConfig']['nodeInfo']['basePort']


def get_own_ip_from_config(config: Dict) -> Optional[str]:
    if is_fair():
        current_nodes = get_fair_current_nodes(config)
    else:
        current_nodes = get_schain_current_nodes(config)
    own_id = config['skaleConfig']['nodeInfo']['nodeID']
    for node_data in current_nodes:
        if node_data['nodeID'] == own_id:
            return node_data['ip']
    return None


def get_schain_env(ulimit_check=True) -> Dict[str, str]:
    env = {'SEGFAULT_SIGNALS': 'all'}
    if not ulimit_check:
        env.update({'NO_ULIMIT_CHECK': 1})

    if is_fair():
        params = get_static_params_fair()
        is_testnet_reward_activation_address = params['info']['testnet_reward_activation_address']
        if is_testnet_reward_activation_address:
            env.update({'TEST_BLOCK_REWARDS_ACTIVATION': 1})
    return env


def parse_public_key_info(bls_public_key):
    public_key_list = bls_public_key.split(':')
    return {
        'blsPublicKey0': str(public_key_list[0]),
        'blsPublicKey1': str(public_key_list[1]),
        'blsPublicKey2': str(public_key_list[2]),
        'blsPublicKey3': str(public_key_list[3]),
    }


def get_bls_public_keys(schain_name, rotation_id):
    key_file = get_secret_key_share_filepath(schain_name, rotation_id)
    data = read_json(key_file)
    return data['bls_public_keys']
