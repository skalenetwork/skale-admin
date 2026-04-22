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
import os

from skale.types.schain import Schain

from core.schains.limits import get_schain_limit, get_schain_type
from core.schains.types import MetricType
from core.types.chain import ChainName, FairChainName
from tools.constants import CHAIN_STATE_PATH, FILESTORAGE_STATIC_PATH
from tools.constants.containers import SHARED_SPACE_CONTAINER_PATH, SHARED_SPACE_VOLUME_NAME
from tools.docker_utils import DockerUtils
from tools.helper import is_fair

logger = logging.getLogger(__name__)


def is_volume_exists(chain_name: ChainName, passive_node=False, dutils=None):
    dutils = dutils or DockerUtils()
    chain_state = os.path.join(CHAIN_STATE_PATH, chain_name)
    if is_fair():
        return os.path.isdir(chain_state)
    elif passive_node:
        filestorage_static_path_schain = os.path.join(FILESTORAGE_STATIC_PATH, chain_name)
        return os.path.isdir(chain_state) and os.path.islink(filestorage_static_path_schain)
    else:
        return dutils.is_data_volume_exists(chain_name)


def init_fair_volume(chain_name: FairChainName, dutils: DockerUtils | None = None) -> None:
    dutils = dutils or DockerUtils()
    chain_state = os.path.join(CHAIN_STATE_PATH, chain_name)
    if os.path.isdir(chain_state):
        logger.debug(f'Volume already exists: {chain_name}')
    else:
        logger.info(f'Creating volume for chain: {chain_name}')
        ensure_data_dir_path(chain_name)


def init_data_volume(schain: Schain, passive_node: bool = False, dutils: DockerUtils | None = None):
    dutils = dutils or DockerUtils()

    if is_volume_exists(schain.name, passive_node=passive_node, dutils=dutils):
        logger.debug(f'Volume already exists: {schain.name}')
        return

    logger.info(f'Creating volume for schain: {schain.name}')
    if passive_node or is_fair():
        ensure_data_dir_path(schain.name)
    else:
        schain_type = get_schain_type(schain.part_of_node)
        disk_limit = get_schain_limit(schain_type, MetricType.disk)
        dutils.create_data_volume(schain.name, disk_limit)


def ensure_data_dir_path(chain_name: ChainName) -> None:
    chain_state = os.path.join(CHAIN_STATE_PATH, chain_name)
    os.makedirs(chain_state, exist_ok=True)
    if not is_fair():
        schain_filestorage_state = os.path.join(chain_state, 'filestorage')
        filestorage_static_path_schain = os.path.join(FILESTORAGE_STATIC_PATH, chain_name)
        if os.path.islink(filestorage_static_path_schain):
            os.unlink(filestorage_static_path_schain)
        os.symlink(
            schain_filestorage_state, filestorage_static_path_schain, target_is_directory=True
        )


def get_schain_volume_config(name: str, mount_path: str, mode=None, passive_node=False):
    mode = mode or 'rw'
    if passive_node or is_fair():
        datadir_src = os.path.join(CHAIN_STATE_PATH, name)
        shared_space_src = os.path.join(CHAIN_STATE_PATH, SHARED_SPACE_VOLUME_NAME)
    else:
        datadir_src = name
        shared_space_src = SHARED_SPACE_VOLUME_NAME

    config = {
        datadir_src: {'bind': mount_path, 'mode': mode},
        shared_space_src: {'bind': SHARED_SPACE_CONTAINER_PATH, 'mode': mode},
    }
    return config
