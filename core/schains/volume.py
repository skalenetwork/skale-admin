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
import shutil

from skale.contracts.manager.schains import SchainStructure
from core.schains.limits import get_schain_limit, get_schain_type
from core.schains.types import MetricType
from tools.configs.schains import SCHAIN_STATE_PATH, SCHAIN_STATIC_PATH
from tools.configs.containers import (
    SHARED_SPACE_VOLUME_NAME,
    SHARED_SPACE_CONTAINER_PATH
)

from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


def is_volume_exists(schain_name, sync_node=False, dutils=None):
    dutils = dutils or DockerUtils()
    if sync_node:
        schain_state = os.path.join(SCHAIN_STATE_PATH, schain_name)
        schain_static_path = os.path.join(SCHAIN_STATIC_PATH, schain_name)
        return os.path.isdir(schain_state) and os.path.islink(schain_static_path)
    else:
        return dutils.is_data_volume_exists(schain_name)


def init_data_volume(
    schain: SchainStructure,
    sync_node: bool = False,
    dutils: DockerUtils = None
):
    dutils = dutils or DockerUtils()

    if is_volume_exists(schain.name, sync_node=sync_node, dutils=dutils):
        logger.debug(f'Volume already exists: {schain.name}')
        return

    logger.info(f'Creating volume for schain: {schain.name}')
    if sync_node:
        ensure_data_dir_path(schain.name)
    else:
        schain_type = get_schain_type(schain.part_of_node)
        disk_limit = get_schain_limit(schain_type, MetricType.disk)
        dutils.create_data_volume(schain.name, disk_limit)


def remove_data_dir(schain_name):
    schain_state = os.path.join(SCHAIN_STATE_PATH, schain_name)
    schain_static_path = os.path.join(SCHAIN_STATIC_PATH, schain_name)
    os.remove(schain_static_path)
    shutil.rmtree(schain_state)


def ensure_data_dir_path(schain_name: str) -> None:
    schain_state = os.path.join(SCHAIN_STATE_PATH, schain_name)
    os.makedirs(schain_state, exist_ok=True)
    schain_filestorage_state = os.path.join(schain_state, 'filestorage')
    schain_static_path = os.path.join(SCHAIN_STATIC_PATH, schain_name)
    if os.path.islink(schain_static_path):
        os.unlink(schain_static_path)
    os.symlink(
        schain_filestorage_state,
        schain_static_path,
        target_is_directory=True
    )


def get_schain_volume_config(name, mount_path, mode=None, sync_node=False):
    mode = mode or 'rw'
    if sync_node:
        datadir_src = os.path.join(SCHAIN_STATE_PATH, name)
        shared_space_src = os.path.join(SCHAIN_STATE_PATH, SHARED_SPACE_VOLUME_NAME)
    else:
        datadir_src = name
        shared_space_src = SHARED_SPACE_VOLUME_NAME

    config = {
        datadir_src: {'bind': mount_path, 'mode': mode},
        shared_space_src: {
            'bind': SHARED_SPACE_CONTAINER_PATH,
            'mode': mode
        }
    }
    return config
