#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
import json
import logging
from pathlib import Path

from tools.configs import SCHAIN_CONFIG_DIR_SKALED
from tools.configs.schains import (
    SCHAINS_DIR_PATH, SCHAINS_DIR_PATH_HOST, BASE_SCHAIN_CONFIG_FILEPATH, SKALED_STATUS_FILENAME,
    SCHAIN_SCHECKS_FILENAME
)


logger = logging.getLogger(__name__)


def _config_filename(name: str) -> str:
    return f'schain_{name}.json'


def schain_config_dir(name: str) -> str:
    """Get sChain config directory path in container"""
    return os.path.join(SCHAINS_DIR_PATH, name)


def schain_config_dir_host(name: str) -> str:
    """Get sChain config directory path on host"""
    return os.path.join(SCHAINS_DIR_PATH_HOST, name)


def init_schain_config_dir(name: str) -> str:
    """Init empty sChain config directory"""
    logger.info(f'Initializing config directory for sChain: {name}')
    data_dir_path = schain_config_dir(name)
    path = Path(data_dir_path)
    os.makedirs(path, exist_ok=True)


def schain_config_filepath(name: str, in_schain_container=False) -> str:
    schain_dir_path = SCHAIN_CONFIG_DIR_SKALED if in_schain_container else schain_config_dir(name)
    return os.path.join(schain_dir_path, _config_filename(name))


def skaled_status_filepath(name: str) -> str:
    return os.path.join(schain_config_dir(name), SKALED_STATUS_FILENAME)


def get_tmp_schain_config_filepath(schain_name):
    schain_dir_path = schain_config_dir(schain_name)
    return os.path.join(schain_dir_path,
                        f'tmp_schain_{schain_name}.json')


def get_schain_check_filepath(schain_name):
    schain_dir_path = schain_config_dir(schain_name)
    return os.path.join(schain_dir_path, SCHAIN_SCHECKS_FILENAME)


def get_schain_config(schain_name):
    config_filepath = schain_config_filepath(schain_name)
    with open(config_filepath) as f:
        schain_config = json.load(f)
    return schain_config


def schain_config_exists(schain_name):
    config_filepath = schain_config_filepath(schain_name)
    return os.path.isfile(config_filepath)


def read_base_config():
    json_data = open(BASE_SCHAIN_CONFIG_FILEPATH).read()
    return json.loads(json_data)
