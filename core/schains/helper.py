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

import os
import logging
import json
from pathlib import Path

from tools.configs.schains import (SCHAINS_DIR_PATH, DATA_DIR_NAME, BASE_SCHAIN_CONFIG_FILEPATH,
                                   IMA_DATA_FILEPATH)
from tools.configs.ima import PROXY_ABI_FILENAME

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
    return os.path.join(schain_dir_path,
                        f'schain_{schain_name}.json')


def schain_config_exists(schain_name):
    schain_config_filepath = get_schain_config_filepath(schain_name)
    return os.path.isfile(schain_config_filepath)


def get_schain_proxy_file_path(schain_name):
    schain_dir_path = get_schain_dir_path(schain_name)
    return os.path.join(schain_dir_path, PROXY_ABI_FILENAME)


def read_base_config():
    json_data = open(BASE_SCHAIN_CONFIG_FILEPATH).read()
    return json.loads(json_data)


def read_ima_data():
    with open(IMA_DATA_FILEPATH) as f:
        return json.load(f)


def get_schain_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpRpcPort"]), int(node_info["wsRpcPort"])


def get_schain_ssl_rpc_ports(schain_id):
    schain_config = get_schain_config(schain_id)
    node_info = schain_config["skaleConfig"]["nodeInfo"]
    return int(node_info["httpsRpcPort"]), int(node_info["wssRpcPort"])
