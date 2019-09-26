#   -*- coding: utf-8 -*-
#
#   This file is part of skale-node
#
#   Copyright (C) 2019 SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import logging
import json
from pathlib import Path

from web3 import Web3

from tools.config import SCHAINS_DIR_PATH, DATA_DIR_NAME, HEALTHCHECK_FILENAME, HEALTHCHECK_STATUSES, \
    BASE_SCHAIN_CONFIG_FILEPATH, PROXY_ABI_FILENAME

logger = logging.getLogger(__name__)

def get_schain_dir_path(schain_name):
    return os.path.join(SCHAINS_DIR_PATH, schain_name)


def get_schain_data_dir(schain_name):
    return os.path.join(get_schain_dir_path(schain_name), DATA_DIR_NAME)


def init_schain_dir(schain_name):
    logger.info(f'Creating data_dir for sChain: {schain_name}')
    data_dir_path = get_schain_data_dir(schain_name)
    path = Path(data_dir_path)
    os.makedirs(path, exist_ok=True)


def get_schain_config_filepath(schain_name):
    schain_dir_path = get_schain_dir_path(schain_name)
    return os.path.join(schain_dir_path, construct_schain_config_filename(schain_name))


def construct_schain_config_filename(schain_name):
    return f'schain_{schain_name}.json'


def get_schain_config(schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    with open(config_filepath) as f:
        schain_config = json.load(f)
    return schain_config


def get_healthcheck_file_path(schain_name):
    schain_dir_path = get_schain_dir_path(schain_name)
    return os.path.join(schain_dir_path, DATA_DIR_NAME, HEALTHCHECK_FILENAME)


def get_healthcheck_value(schain_name):
    file_path = get_healthcheck_file_path(schain_name)

    if not os.path.isfile(file_path):
        return -1

    f = open(file_path, "r")
    value = f.read()

    return value.rstrip()


def get_healthcheck_name(value):
    return HEALTHCHECK_STATUSES.get(str(value), HEALTHCHECK_STATUSES['-2'])


def get_schain_proxy_file_path(schain_name):
    schain_dir_path = get_schain_dir_path(schain_name)
    return os.path.join(schain_dir_path, PROXY_ABI_FILENAME)


def read_base_config():
    json_data = open(BASE_SCHAIN_CONFIG_FILEPATH).read()
    return json.loads(json_data)


def add_accounts_to_base_config(base_config, allocation):
    base_config['accounts'] = {**base_config['accounts'], **allocation}
    return base_config


def add_to_allocation(allocation, account, amount, code=None, storage={}, nonce=0):
    assert type(code) is str or code is None
    assert type(storage) is dict or storage is None
    acc_fx = Web3.toChecksumAddress(account)
    if str(acc_fx) not in allocation:
        allocation[acc_fx] = {"balance": str(amount)}
        if code:
            allocation[acc_fx]['code'] = code
            allocation[acc_fx]['storage'] = storage
            allocation[acc_fx]['nonce'] = str(nonce)


def get_schain_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpRpcPort"]), int(node_info["wsRpcPort"])

def get_schain_ssl_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpsRpcPort"]), int(node_info["wssRpcPort"])
