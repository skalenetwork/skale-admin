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
from core.node_config import NodeConfig
from core.schains.config.directory import get_files_with_prefix, schain_config_dir
from core.schains.config.file_manager import ConfigFileManager, SkaledConfigFilename
from core.schains.config.generator import generate_schain_config_with_skale

from tools.configs import SCHAIN_CONFIG_DIR_SKALED
from tools.str_formatters import arguments_list_string
from tools.node_options import NodeOptions

from web.models.schain import upsert_schain_record


logger = logging.getLogger(__name__)


def create_new_upstream_config(
    skale: Skale,
    node_config: NodeConfig,
    schain_name: str,
    generation: int,
    ecdsa_sgx_key_name: str,
    rotation_data: dict,
    sync_node: bool,
    node_options: NodeOptions
) -> Dict:
    logger.warning(arguments_list_string({
        'sChain name': schain_name,
        'generation': generation,
        'sync_node': sync_node
        }, 'Generating sChain config'))

    schain_config = generate_schain_config_with_skale(
        skale=skale,
        schain_name=schain_name,
        generation=generation,
        node_config=node_config,
        rotation_data=rotation_data,
        ecdsa_key_name=ecdsa_sgx_key_name,
        sync_node=sync_node,
        node_options=node_options
    )
    return schain_config.to_dict()


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


def get_upstream_config_rotation_ids(file_manager: ConfigFileManager) -> List[int]:
    logger.debug('Retrieving upstream rotation_ids')
    config = file_manager.latest_upstream_config
    return get_rotation_ids_from_config(config)


def get_skaled_config_rotations_ids(file_manager: ConfigFileManager) -> List[int]:
    logger.debug('Retrieving rotation_ids')
    config = file_manager.skaled_config
    return get_rotation_ids_from_config(config)


def get_latest_finish_ts(config: Dict) -> Optional[int]:
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


def get_finish_ts_from_latest_upstream(file_manager: ConfigFileManager) -> Optional[int]:
    config = file_manager.latest_upstream_config
    if not config:
        return None
    return get_latest_finish_ts(config)


def get_finish_ts_from_skaled_config(file_manager: ConfigFileManager) -> Optional[int]:
    config = file_manager.skaled_config
    return get_latest_finish_ts(config)


def get_number_of_secret_shares(schain_name: str) -> int:
    config_dir = schain_config_dir(schain_name)
    prefix = 'secret_key_'
    return len(get_files_with_prefix(config_dir, prefix))


def get_skaled_container_config_path(schain_name: str) -> str:
    return SkaledConfigFilename(schain_name).abspath(SCHAIN_CONFIG_DIR_SKALED)
