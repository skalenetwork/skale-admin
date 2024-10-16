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

import logging

from skale.contracts.manager.schains import SchainStructure

from core.schains.runner import restart_container
from core.schains.runner import is_container_exists, is_container_running
from tools.docker_utils import DockerUtils

from tools.configs.schains import MAX_SCHAIN_FAILED_RPC_COUNT
from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER
)

logger = logging.getLogger(__name__)


def handle_failed_schain_rpc(
    schain: SchainStructure,
    schain_record,
    skaled_status,
    dutils=None
):
    dutils = dutils or DockerUtils()
    logger.info(f'Monitoring RPC for sChain {schain.name}')

    if not is_container_exists(schain.name, dutils=dutils):
        logger.warning(f'{schain.name} RPC monitor failed: container doesn\'t exit')
        return

    if not is_container_running(schain.name, dutils=dutils):
        logger.warning(f'{schain.name} RPC monitor failed: container is not running')
        return

    if skaled_status.exit_time_reached:
        logger.info(f'{schain.name} - Skipping RPC monitor: exit time reached')
        skaled_status.log()
        schain_record.set_failed_rpc_count(0)
        return

    if skaled_status.downloading_snapshot:
        logger.info(f'{schain.name} - Skipping RPC monitor: downloading snapshot')
        skaled_status.log()
        schain_record.set_failed_rpc_count(0)
        return

    rpc_stuck = schain_record.failed_rpc_count > MAX_SCHAIN_FAILED_RPC_COUNT
    logger.info(
        'SChain %s, rpc stuck: %s, failed_rpc_count: %d, restart_count: %d',
        schain.name,
        rpc_stuck,
        schain_record.failed_rpc_count,
        schain_record.restart_count
    )
    if rpc_stuck:
        if schain_record.restart_count < MAX_SCHAIN_RESTART_COUNT:
            logger.info(f'SChain {schain.name}: restarting container')
            restart_container(SCHAIN_CONTAINER, schain, dutils=dutils)
            schain_record.set_restart_count(schain_record.restart_count + 1)
        else:
            logger.warning(f'SChain {schain.name}: max restart count exceeded')
        schain_record.set_failed_rpc_count(0)
    else:
        schain_record.set_failed_rpc_count(schain_record.failed_rpc_count + 1)
