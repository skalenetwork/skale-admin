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

import filecmp
import glob
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from tools.configs import SCHAIN_CONFIG_DIR_SKALED
from tools.configs.schains import (
    SCHAINS_DIR_PATH, SCHAINS_DIR_PATH_HOST, BASE_SCHAIN_CONFIG_FILEPATH, SKALED_STATUS_FILENAME,
    SCHAIN_SCHECKS_FILENAME
)
from tools.helper import read_json, write_json


logger = logging.getLogger(__name__)


config_lock = threading.Lock()


def config_filename(name: str) -> str:
    return f'schain_{name}.json'


def upstream_prefix(name: str) -> str:
    return f'schain_{name}_'


def upstream_rotation_version_prefix(name: str, rotation_id: int, version: str) -> str:
    return f'schain_{name}_{rotation_id}_{version}_'


def formatted_stream_version(stream_version: str) -> str:
    return stream_version.replace('.', '_')


def new_config_filename(name: str, rotation_id: int, stream_version: str) -> str:
    ts = int(time.time())
    formatted_version = formatted_stream_version(stream_version)
    return f'schain_{name}_{rotation_id}_{formatted_version}_{ts}.json'


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
    return os.path.join(schain_dir_path, config_filename(name))


def get_schain_config(schain_name, path: Optional[str] = None) -> Optional[Dict]:
    config_path = path or schain_config_filepath(schain_name)
    config = None
    with config_lock:
        if config_path is None or not os.path.isfile(config_path):
            return None
        return read_json(config_path)
    return config


def get_upstream_config_filepath(schain_name) -> Optional[str]:
    config_dir = schain_config_dir(schain_name)
    prefix = upstream_prefix(schain_name)
    dir_files = get_files_with_prefix(config_dir, prefix)
    if not dir_files:
        return None
    return os.path.join(config_dir, dir_files[-1])


def get_upstream_schain_config(schain_name) -> Optional[Dict]:
    upstream_path = get_upstream_config_filepath(schain_name)
    config = None
    with config_lock:
        if upstream_path is None or not os.path.isfile(upstream_path):
            return None
        return read_json(upstream_path)
    return config


def new_schain_config_filepath(
    name: str,
    rotation_id: int,
    stream_version: str,
    in_schain_container: bool = False
) -> str:
    schain_dir_path = SCHAIN_CONFIG_DIR_SKALED if in_schain_container else schain_config_dir(name)
    return os.path.join(schain_dir_path, new_config_filename(name, rotation_id, stream_version))


def upstreams_for_rotation_id_version(
    name: str,
    rotation_id: int,
    stream_version: str
) -> List[str]:
    schain_dir_path = schain_config_dir(name)
    version = formatted_stream_version(stream_version)
    prefix = upstream_rotation_version_prefix(name, rotation_id, version)
    pattern = os.path.join(schain_dir_path, prefix + '*.json')
    with config_lock:
        return glob.glob(pattern)


def skaled_status_filepath(name: str) -> str:
    return os.path.join(schain_config_dir(name), SKALED_STATUS_FILENAME)


def get_tmp_schain_config_filepath(schain_name):
    schain_dir_path = schain_config_dir(schain_name)
    return os.path.join(schain_dir_path,
                        f'tmp_schain_{schain_name}.json')


def get_schain_check_filepath(schain_name):
    schain_dir_path = schain_config_dir(schain_name)
    return os.path.join(schain_dir_path, SCHAIN_SCHECKS_FILENAME)


def schain_config_exists(schain_name):
    config_filepath = schain_config_filepath(schain_name)
    with config_lock:
        return os.path.isfile(config_filepath)


def read_base_config():
    json_data = open(BASE_SCHAIN_CONFIG_FILEPATH).read()
    return json.loads(json_data)


def get_files_with_prefix(config_dir: str, prefix: str) -> List[str]:
    prefix_files = []
    with config_lock:
        if os.path.isdir(config_dir):
            configs = [
                os.path.join(config_dir, fname)
                for fname in os.listdir(config_dir)
                if fname.startswith(prefix)
            ]
            prefix_files = sorted(configs)
    return prefix_files


def sync_config_with_file(schain_name: str, src_path: str) -> None:
    dst_path = schain_config_filepath(schain_name)
    with config_lock:
        shutil.copy(src_path, dst_path)


def save_schain_config(schain_config, schain_name):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    write_json(tmp_config_filepath, schain_config)
    config_filepath = schain_config_filepath(schain_name)
    with config_lock:
        shutil.move(tmp_config_filepath, config_filepath)


def save_new_schain_config(schain_config, schain_name, rotation_id, stream_version):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    write_json(tmp_config_filepath, schain_config)
    config_filepath = new_schain_config_filepath(schain_name, rotation_id, stream_version)
    with config_lock:
        shutil.move(tmp_config_filepath, config_filepath)


def config_synced_with_upstream(name: str) -> bool:
    upstream_path = get_upstream_config_filepath(name)
    config_path = schain_config_filepath(name)
    logger.debug('Checking if %s updated according to %s', config_path, upstream_path)
    if not upstream_path:
        return True
    with config_lock:
        return filecmp.cmp(upstream_path, config_path)
