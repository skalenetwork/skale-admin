#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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
from apscheduler.schedulers.background import BackgroundScheduler

from skale import FairManager
from skale.transactions.exceptions import TransactionError
from tools.configs.fair import (
    HEALTHCHECK_JOB_NAME,
    SAFE_HEARTBEAT_BUFFER,
)
from tools.exceptions import LocalEndpointUnreachableError

from core.node_config import NodeConfig
from core.utils.fair import init_local_fair


logger = logging.getLogger(__name__)


def healthcheck_job(
    local_fair: FairManager,
) -> None:
    logger.info('Running healthcheck job')
    try:
        res = local_fair.status.alive()
        logger.info(f'Healthcheck tx result: {res}')
    except TransactionError as e:
        logger.exception(f'Healthcheck failed: {e}')


def handle_healthcheck_job(
    scheduler: BackgroundScheduler,
    node_config: NodeConfig,
) -> None:
    try:
        job = scheduler.get_job(HEALTHCHECK_JOB_NAME)
        if job is None:
            local_fair = init_local_fair(node_config)
            logger.info('Going to execute healthcheck job')
            healthcheck_job(local_fair)
            logger.info('Adding healthcheck job to the scheduler')
            heartbeat_interval = local_fair.status.heartbeat_interval()
            safe_heartbeat_interval = heartbeat_interval - SAFE_HEARTBEAT_BUFFER
            logger.info(f'Healthcheck job will run every {heartbeat_interval} seconds')
            logger.info(
                'Scheduling healthcheck job, interval: %d seconds, job id: %s',
                safe_heartbeat_interval,
                HEALTHCHECK_JOB_NAME,
            )
            scheduler.add_job(
                func=healthcheck_job,
                args=[local_fair],
                trigger='interval',
                seconds=safe_heartbeat_interval,
                id=HEALTHCHECK_JOB_NAME,
                name='fair healthcheck job',
            )
            scheduler.start()
            logger.info('Healthcheck scheduler started - jobs will now execute')
        else:
            logger.info('Healthcheck job already exists in the scheduler, skipping')
    except LocalEndpointUnreachableError as e:
        logger.exception(f'Local endpoint unreachable: {e}, cannot start healthcheck job')
