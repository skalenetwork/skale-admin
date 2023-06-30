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

import logging
import time

from core.schains.volume import is_volume_exists
from core.schains.runner import (
    get_image,
    get_new_image,
    is_container_exists,
    is_schain_container_failed,
    remove_container,
    restart_container,
    run_ima_container,
    run_schain_container
)
from core.ima.schain import copy_schain_ima_abi
from core.schains.ima import get_migration_ts, ImaData

from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER,
    IMA_CONTAINER
)
from tools.configs.ima import DISABLE_IMA
from tools.docker_utils import DockerUtils


logger = logging.getLogger(__name__)


def monitor_schain_container(
    schain,
    schain_record,
    skaled_status,
    public_key=None,
    start_ts=None,
    dutils=None
) -> None:
    dutils = dutils or DockerUtils()
    schain_name = schain['name']
    logger.info(f'Monitoring container for sChain {schain_name}')

    if not is_volume_exists(schain_name, dutils=dutils):
        logger.error(f'Data volume for sChain {schain_name} does not exist')
        return

    if not is_container_exists(schain_name, dutils=dutils):
        logger.info(f'SChain {schain_name}: container doesn\'t exits')
        run_schain_container(
            schain=schain,
            public_key=public_key,
            start_ts=start_ts,
            snapshot_from=schain_record.snapshot_from,
            dutils=dutils
        )
        schain_record.reset_failed_conunters()
        return

    if skaled_status.exit_time_reached:
        logger.info(f'{schain_name} - Skipping container monitor: exit time reached')
        skaled_status.log()
        schain_record.reset_failed_conunters()
        return

    if skaled_status.clear_data_dir and skaled_status.start_from_snapshot:
        logger.info(f'{schain_name} - Skipping container monitor: sChain should be repaired')
        skaled_status.log()
        schain_record.reset_failed_conunters()
        return

    if is_schain_container_failed(schain_name, dutils=dutils):
        if schain_record.restart_count < MAX_SCHAIN_RESTART_COUNT:
            logger.info(f'SChain {schain_name}: restarting container')
            restart_container(SCHAIN_CONTAINER, schain, dutils=dutils)
            schain_record.set_restart_count(schain_record.restart_count + 1)
            schain_record.set_failed_rpc_count(0)
        else:
            logger.warning(
                'SChain %s: max restart count exceeded - %d',
                schain_name,
                MAX_SCHAIN_RESTART_COUNT
            )


def monitor_ima_container(
    schain: dict,
    ima_data: ImaData,
    dutils: DockerUtils = None
) -> None:
    schain_name = schain["name"]

    if DISABLE_IMA:
        logger.info(f'{schain_name} - IMA is disabled, skipping')
        return

    if not ima_data.linked:
        logger.info(f'{schain_name} - not registered in IMA, skipping')
        return

    copy_schain_ima_abi(schain_name)

    container_exists = is_container_exists(schain_name, container_type=IMA_CONTAINER, dutils=dutils)
    image = get_image(type=IMA_CONTAINER)

    migration_ts = get_migration_ts(schain_name)
    if time.time() > migration_ts:
        image = get_new_image(type=IMA_CONTAINER)
        if container_exists:
            remove_container(schain_name, IMA_CONTAINER, dutils)
            container_exists = False
    if not container_exists:
        logger.info(f'sChain {schain_name}: IMA container doesn\'t exits, creating...')
        run_ima_container(
            schain,
            ima_data.chain_id,
            image=image,
            dutils=dutils
        )
    else:
        logger.warning(f'sChain {schain_name}: IMA container exists, but not running, skipping')
