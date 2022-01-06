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

from core.schains.runner import restart_container
from core.schains.runner import is_container_exists, is_exited_with_zero
from tools.docker_utils import DockerUtils

from tools.configs.schains import MAX_SCHAIN_FAILED_RPC_COUNT
from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER
)

logger = logging.getLogger(__name__)


def monitor_schain_rpc(
    schain,
    schain_record,
    skaled_status,
    dutils=None
):
    dutils = dutils or DockerUtils()
    schain_name = schain['name']
    logger.info(f'Monitoring RPC for sChain {schain_name}')

    if not is_container_exists(schain_name, dutils=dutils):
        logger.warning(f'{schain_name} RPC monitor failed: container doesn\'t exit')
        return

    if is_exited_with_zero(schain_name, dutils=dutils):
        logger.info(f'{schain_name} - Skipping RPC monitor: container exited with zero EC')
        return

    if skaled_status.is_downloading_snapshot:
        logger.info(f'{schain_name} - Skipping RPC monitor: skaled is downloading snapshot')
        return

    rpc_stuck = schain_record.failed_rpc_count > MAX_SCHAIN_FAILED_RPC_COUNT
    logger.info(
        'SChain %s, rpc stuck: %s, failed_rpc_count: %d, restart_count: %d',
        schain_name,
        rpc_stuck,
        schain_record.failed_rpc_count,
        schain_record.restart_count
    )
    if rpc_stuck:
        if schain_record.restart_count < MAX_SCHAIN_RESTART_COUNT:
            logger.info(f'SChain {schain_name}: restarting container')
            restart_container(SCHAIN_CONTAINER, schain, dutils=dutils)
            schain_record.set_restart_count(schain_record.restart_count + 1)
        else:
            logger.warning(f'SChain {schain_name}: max restart count exceeded')
        schain_record.set_failed_rpc_count(0)
    else:
        schain_record.set_failed_rpc_count(schain_record.failed_rpc_count + 1)
