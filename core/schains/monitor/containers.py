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
from typing import Optional
from skale.contracts.manager.schains import SchainStructure

from core.schains.volume import is_volume_exists
from core.schains.runner import (
    get_container_image,
    get_ima_container_time_frame,
    get_image_name,
    is_container_exists,
    is_schain_container_failed,
    remove_container,
    restart_container,
    run_ima_container,
    run_schain_container
)
from core.ima.schain import copy_schain_ima_abi
from core.schains.ima import get_ima_time_frame, ImaData
from core.schains.ssl import update_ssl_change_date

from tools.configs import SYNC_NODE
from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER,
    IMA_CONTAINER
)
from tools.docker_utils import DockerUtils


logger = logging.getLogger(__name__)


def monitor_schain_container(
    schain: SchainStructure,
    schain_record,
    skaled_status,
    download_snapshot=False,
    start_ts=None,
    abort_on_exit: bool = True,
    dutils: Optional[DockerUtils] = None,
    sync_node: bool = False,
    historic_state: bool = False
) -> None:
    dutils = dutils or DockerUtils()
    schain.name = schain.name
    logger.info(f'Monitoring container for sChain {schain.name}')

    if not is_volume_exists(schain.name, sync_node=sync_node, dutils=dutils):
        logger.error(f'Data volume for sChain {schain.name} does not exist')
        return

    if skaled_status.exit_time_reached and abort_on_exit:
        logger.info(
            f'{schain.name} - Skipping container monitor: exit time reached')
        skaled_status.log()
        schain_record.reset_failed_counters()
        return

    if not is_container_exists(schain.name, dutils=dutils):
        logger.info(f'SChain {schain.name}: container doesn\'t exits')
        run_schain_container(
            schain=schain,
            download_snapshot=download_snapshot,
            start_ts=start_ts,
            dutils=dutils,
            snapshot_from=schain_record.snapshot_from,
            sync_node=sync_node,
            historic_state=historic_state,
        )
        update_ssl_change_date(schain_record)
        schain_record.reset_failed_counters()
        return

    if skaled_status.clear_data_dir and skaled_status.start_from_snapshot:
        logger.info(
            f'{schain.name} - Skipping container monitor: sChain should be repaired')
        skaled_status.log()
        schain_record.reset_failed_counters()
        return

    if is_schain_container_failed(schain.name, dutils=dutils):
        if schain_record.restart_count < MAX_SCHAIN_RESTART_COUNT:
            logger.info('sChain %s: restarting container', schain.name)
            restart_container(SCHAIN_CONTAINER, schain, dutils=dutils)
            update_ssl_change_date(schain_record)
            schain_record.set_restart_count(schain_record.restart_count + 1)
            schain_record.set_failed_rpc_count(0)
        else:
            logger.warning(
                'SChain %s: max restart count exceeded - %d',
                schain.name,
                MAX_SCHAIN_RESTART_COUNT
            )
    else:
        schain_record.set_restart_count(0)


def monitor_ima_container(
    schain: dict,
    ima_data: ImaData,
    migration_ts: int = 0,
    dutils: DockerUtils = None
) -> None:

    if SYNC_NODE:
        return

    if not ima_data.linked:
        logger.info(f'{schain.name} - not registered in IMA, skipping')
        return

    copy_schain_ima_abi(schain.name)

    container_exists = is_container_exists(
        schain.name, container_type=IMA_CONTAINER, dutils=dutils)

    if time.time() > migration_ts:
        logger.debug('IMA migration time passed')

        image = get_image_name(image_type=IMA_CONTAINER, new=True)
        time_frame = get_ima_time_frame(schain.name, after=True)
        if container_exists:
            container_image = get_container_image(schain.name, IMA_CONTAINER, dutils)
            container_time_frame = get_ima_container_time_frame(schain.name, dutils)

            if image != container_image or time_frame != container_time_frame:
                logger.info('Removing old container as part of IMA migration')
                remove_container(schain.name, IMA_CONTAINER, dutils)
                container_exists = False
    else:
        time_frame = get_ima_time_frame(schain.name, after=False)
        image = get_image_name(image_type=IMA_CONTAINER, new=False)
    logger.debug('IMA time frame %d', time_frame)

    if not container_exists:
        logger.info(
            '%s No IMA container, creating, image %s, time frame %d',
            schain.name, image, time_frame
        )
        run_ima_container(
            schain,
            ima_data.chain_id,
            image=image,
            time_frame=time_frame,
            dutils=dutils
        )
    else:
        logger.debug(
            'sChain %s: IMA container exists, but not running, skipping', schain.name)
