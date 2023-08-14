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

import json
import logging
import os
from pathlib import Path
from typing import List

from tools.configs.schains import (
    BASE_SCHAIN_CONFIG_FILEPATH,
    SCHAINS_DIR_PATH,
    SCHAINS_DIR_PATH_HOST,
    SCHAIN_SCHECKS_FILENAME,
    SKALED_STATUS_FILENAME
)


logger = logging.getLogger(__name__)


def schain_config_dir(name: str) -> str:
    """Get sChain config directory path in container"""
    return os.path.join(SCHAINS_DIR_PATH, name)


def schain_config_dir_host(name: str) -> str:
    """Get sChain config directory path on host"""
    return os.path.join(SCHAINS_DIR_PATH_HOST, name)


def init_schain_config_dir(name: str) -> str:
    """Init empty sChain config directory"""
    logger.debug(f'Initializing config directory for sChain: {name}')
    data_dir_path = schain_config_dir(name)
    path = Path(data_dir_path)
    os.makedirs(path, exist_ok=True)
    return data_dir_path


def skaled_status_filepath(name: str) -> str:
    return os.path.join(schain_config_dir(name), SKALED_STATUS_FILENAME)


def get_schain_check_filepath(schain_name):
    schain_dir_path = schain_config_dir(schain_name)
    return os.path.join(schain_dir_path, SCHAIN_SCHECKS_FILENAME)


def read_base_config():
    json_data = open(BASE_SCHAIN_CONFIG_FILEPATH).read()
    return json.loads(json_data)


def get_files_with_prefix(config_dir: str, prefix: str) -> List[str]:
    prefix_files = []
    if os.path.isdir(config_dir):
        configs = [
            os.path.join(config_dir, fname)
            for fname in os.listdir(config_dir)
            if fname.startswith(prefix)
        ]
        prefix_files = sorted(configs)
    return prefix_files
