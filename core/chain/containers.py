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

import time
import logging
from typing import Optional, cast

from core.redis.chain_record import ChainRecord
from core.chain.status import SkaledStatus
from core.chain.volume import is_volume_exists
from core.chain.runner import (
    get_container_image,
    get_ima_container_time_frame,
    get_image_name,
    is_container_exists,
    is_skaled_container_failed,
    remove_container,
    restart_container,
    run_ima_container,
    run_skaled_container,
)
from core.schains.ima import get_ima_time_frame, ImaData
from core.chain.ssl import update_ssl_change_date

from core.types.chain import ChainName
from tools.configs import PASSIVE_NODE
from tools.configs.containers import MAX_SKALED_RESTART_COUNT, SKALED_CONTAINER, IMA_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import is_fair

from web.models.schain import SChainRecord


logger = logging.getLogger(__name__)


def monitor_skaled_container(
    chain_name: ChainName,
    chain_record: SChainRecord | ChainRecord,
    skaled_status: SkaledStatus,
    download_snapshot=False,
    start_ts=None,
    snapshot_from: Optional[str] = None,
    abort_on_exit: bool = True,
    dutils: Optional[DockerUtils] = None,
    passive_node: bool = False,
    historic_state: bool = False,
) -> None:
    dutils = dutils or DockerUtils()
    logger.info(f'Monitoring skaled container for {chain_name}')

    if not is_volume_exists(chain_name, passive_node=passive_node, dutils=dutils):
        logger.error(f'Data volume for chain {chain_name} does not exist')
        return

    if skaled_status.exit_time_reached and abort_on_exit:
        logger.info(f'{chain_name} - Skipping container monitor: exit time reached')
        skaled_status.log()
        chain_record.reset_failed_counters()
        return

    if not is_container_exists(chain_name, dutils=dutils):
        logger.info(f"Chain {chain_name}: container doesn't exist")
        run_skaled_container(
            chain_name=chain_name,
            download_snapshot=download_snapshot,
            start_ts=start_ts,
            dutils=dutils,
            snapshot_from=snapshot_from,
            passive_node=passive_node,
            historic_state=historic_state,
        )
        update_ssl_change_date(chain_record)
        chain_record.reset_failed_counters()
        chain_record.set_force_skaled_start(False)
        return

    if skaled_status.clear_data_dir and skaled_status.start_from_snapshot:
        logger.info(f'{chain_name} - Skipping container monitor: skaled should be repaired')
        skaled_status.log()
        chain_record.reset_failed_counters()
        return

    if is_skaled_container_failed(chain_name, dutils=dutils):
        restart_count = cast(int, chain_record.restart_count)
        if restart_count < MAX_SKALED_RESTART_COUNT:
            logger.info('Chain %s: restarting container', chain_name)
            restart_container(SKALED_CONTAINER, chain_name, dutils=dutils)
            update_ssl_change_date(chain_record)
            chain_record.set_restart_count(restart_count + 1)
            chain_record.set_failed_rpc_count(0)
        else:
            logger.warning(
                'Chain %s: max restart count exceeded - %d', chain_name, MAX_SKALED_RESTART_COUNT
            )
    else:
        chain_record.set_restart_count(0)
        chain_record.set_snapshot_from('')


def monitor_ima_container(
    chain_name: ChainName,
    ima_data: ImaData,
    migration_ts: int = 0,
    dutils: DockerUtils | None = None,
) -> None:
    dutils = dutils or DockerUtils()

    if PASSIVE_NODE or is_fair():
        return

    if not ima_data.linked:
        logger.info(f'{chain_name} - not registered in IMA, skipping')
        return

    container_exists = is_container_exists(chain_name, container_type=IMA_CONTAINER, dutils=dutils)

    if time.time() > migration_ts:
        logger.debug('IMA migration time passed')

        image = get_image_name(image_type=IMA_CONTAINER, new=True)
        time_frame = get_ima_time_frame(chain_name, after=True)
        if container_exists:
            container_image = get_container_image(chain_name, IMA_CONTAINER, dutils)
            container_time_frame = get_ima_container_time_frame(chain_name, dutils)

            if image != container_image or time_frame != container_time_frame:
                logger.info('Removing old container as part of IMA migration')
                remove_container(chain_name, IMA_CONTAINER, dutils)
                container_exists = False
    else:
        time_frame = get_ima_time_frame(chain_name, after=False)
        image = get_image_name(image_type=IMA_CONTAINER, new=False)
    logger.debug('IMA time frame %d', time_frame)

    if not container_exists:
        logger.info(
            '%s No IMA container, creating, image %s, time frame %d', chain_name, image, time_frame
        )
        run_ima_container(
            chain_name, ima_data.chain_id, image=image, time_frame=time_frame, dutils=dutils
        )
    else:
        logger.debug('Chain %s: IMA container exists, but not running, skipping', chain_name)
