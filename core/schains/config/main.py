#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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
import os
import shutil
import logging
from typing import Dict, Optional

from skale import Skale

from core.node import get_skale_node_version
from core.schains.config.directory import (
    get_tmp_schain_config_filepath,
    new_config_prefix,
    schain_config_dir,
    schain_config_filepath,
    new_schain_config_filepath
)
from core.schains.config.generator import generate_schain_config_with_skale
from tools.str_formatters import arguments_list_string

from web.models.schain import upsert_schain_record, SChainRecord


logger = logging.getLogger(__name__)


def init_schain_config(
    skale: Skale,
    node_id: int,
    schain_name: str,
    generation: int,
    ecdsa_sgx_key_name: str,
    rotation_data: dict,
    schain_record: SChainRecord
):
    config_filepath = schain_config_filepath(schain_name)

    logger.warning(arguments_list_string({
        'sChain name': schain_name,
        'config_filepath': config_filepath
        }, 'Generating sChain config'))

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        generation=generation,
        node_id=node_id,
        rotation_data=rotation_data,
        ecdsa_key_name=ecdsa_sgx_key_name
    )
    save_schain_config(schain_config.to_dict(), schain_name)
    update_schain_config_version(schain_name, schain_record=schain_record)


def create_new_schain_config(
    skale: Skale,
    node_id: int,
    schain_name: str,
    generation: int,
    ecdsa_sgx_key_name: str,
    rotation_data: dict,
    stream_version: str,
    schain_record: SChainRecord
):
    logger.info('Generating sChain config for %s', schain_name)

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        generation=generation,
        node_id=node_id,
        rotation_data=rotation_data,
        ecdsa_key_name=ecdsa_sgx_key_name
    )
    save_new_schain_config(
        schain_config.to_dict(),
        schain_name,
        rotation_data['rotation_id'],
        stream_version
    )
    update_schain_config_version(schain_name, schain_record=schain_record)


def save_schain_config(schain_config, schain_name):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    with open(tmp_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)
    config_filepath = schain_config_filepath(schain_name)
    shutil.move(tmp_config_filepath, config_filepath)


def save_new_schain_config(schain_config, schain_name, rotation_id, stream_version):
    tmp_config_filepath = get_tmp_schain_config_filepath(schain_name)
    with open(tmp_config_filepath, 'w') as outfile:
        json.dump(schain_config, outfile, indent=4)
    config_filepath = new_schain_config_filepath(schain_name, rotation_id, stream_version)
    shutil.move(tmp_config_filepath, config_filepath)


def sync_config_with_file(schain_name: str, src_path: str) -> None:
    dst_path = schain_config_filepath(schain_name)
    shutil.copy(src_path, dst_path)


def update_schain_config_version(schain_name, schain_record=None):
    new_config_version = get_skale_node_version()
    schain_record = schain_record or upsert_schain_record(schain_name)
    logger.info(f'Going to change config_version for {schain_name}: \
{schain_record.config_version} -> {new_config_version}')
    schain_record.set_config_version(new_config_version)


def schain_config_version_match(schain_name, schain_record=None):
    schain_record = schain_record or upsert_schain_record(schain_name)
    skale_node_version = get_skale_node_version()
    logger.info(f'config check, schain: {schain_name}, config_version: \
{schain_record.config_version}, skale_node_version: {skale_node_version}')
    return schain_record.config_version == skale_node_version


def get_upstream_config_filepath(schain_name) -> Optional[str]:
    config_dir = schain_config_dir(schain_name)
    prefix = new_config_prefix(schain_name)
    dir_files = None
    if os.path.isdir(config_dir):
        configs = [
            os.path.join(config_dir, fname)
            for fname in os.listdir(config_dir)
            if fname.startswith(prefix)
        ]
        dir_files = sorted(
            configs,
        )
    if not dir_files:
        return None
    return os.path.join(config_dir, dir_files[-1])


def get_node_groups_from_config(config_path: str) -> Dict:
    with open(config_path) as upstream_file:
        config = json.load(upstream_file)
        return config['skaleConfig']['sChain']['nodeGroups']


def get_finish_ts(config_path: str) -> Optional[int]:
    if not os.path.isfile(config_path):
        return None
    node_groups = get_node_groups_from_config(config_path)
    last_rotation = sorted(node_groups.keys())[-1]
    return node_groups[last_rotation]['finish_ts']


def get_finish_ts_from_upstream_config(schain_name: str) -> Optional[int]:
    upstream_path = get_upstream_config_filepath(schain_name)
    if upstream_path is None:
        return None
    return get_finish_ts(upstream_path)


def get_finish_ts_from_config(schain_name: str) -> Optional[int]:
    upstream_path = schain_config_filepath(schain_name)
    return get_finish_ts(upstream_path)
