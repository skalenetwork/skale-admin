#
#   -*- coding: utf-8 -*-
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

import logging
from typing import Dict, List, Optional

from skale import Skale

from core.node import get_skale_node_version
from core.schains.config.directory import (
    get_files_with_prefix,
    get_schain_config,
    get_upstream_schain_config,
    save_new_schain_config,
    save_schain_config,
    schain_config_dir,
    schain_config_filepath
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


def get_node_groups_from_config(config: Dict) -> Dict:
    return config['skaleConfig']['sChain']['nodeGroups']


def get_rotation_ids_from_config(config: Optional[Dict]) -> List[int]:
    if not config:
        return []
    node_groups = get_node_groups_from_config(config)
    rotation_ids = list(sorted(map(int, node_groups.keys())))
    return rotation_ids


def get_upstream_rotation_ids(name: str) -> List[int]:
    logger.debug('Retrieving upstream rotation_ids')
    config = get_upstream_schain_config(name)
    return get_rotation_ids_from_config(config)


def get_config_rotations_ids(name: str) -> List[int]:
    logger.debug('Retrieving rotation_ids')
    config = get_schain_config(name)
    return get_rotation_ids_from_config(config)


def get_latest_finish_ts(config: str) -> Optional[int]:
    node_groups = get_node_groups_from_config(config)
    rotation_ids = iter(sorted(map(int, node_groups.keys()), reverse=True))
    finish_ts = None
    try:
        while finish_ts is None:
            rotation_id = next(rotation_ids)
            finish_ts = node_groups[str(rotation_id)]['finish_ts']
    except StopIteration:
        logger.debug('No finish_ts found in config')

    return finish_ts


def get_finish_ts_from_upstream_config(schain_name: str) -> Optional[int]:
    config = get_upstream_schain_config(schain_name)
    if not config:
        return None
    return get_latest_finish_ts(config)


def get_finish_ts_from_config(schain_name: str) -> Optional[int]:
    config = get_schain_config(schain_name)
    return get_latest_finish_ts(config)


def get_number_of_secret_shares(schain_name: str) -> int:
    config_dir = schain_config_dir(schain_name)
    prefix = 'secret_key_'
    return len(get_files_with_prefix(config_dir, prefix))
