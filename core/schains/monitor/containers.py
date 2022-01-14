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


from core.schains.volume import is_volume_exists
from core.schains.runner import (
    is_schain_container_failed,
    restart_container,
    run_schain_container,
    is_container_exists
)
from tools.configs.containers import (
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER
)
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
            dutils=dutils
        )
        schain_record.reset_failed_conunters()
        return

    if skaled_status.exit_time_reached:
        logger.info(f'{schain_name} - Skipping container monitor: exit time reached')
        schain_record.reset_failed_conunters()
        return

    if skaled_status.clear_data_dir and skaled_status.start_from_snapshot:
        logger.info(f'{schain_name} - Skipping container monitor: sChain should be repaired')
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
