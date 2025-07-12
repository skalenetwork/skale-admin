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

from skale import MirageManager
from skale.transactions.exceptions import TransactionError

from core.node_config import NodeConfig
from core.utils.mirage import init_local_mirage


logger = logging.getLogger(__name__)
BACKGROUND_JOB_NAME = 'mirage_healthcheck'
INTERVAL_BUFFER = 20


def healthcheck_job(
    local_mirage: MirageManager,
) -> None:
    logger.info('Running healthcheck job')
    try:
        res = local_mirage.status.alive()
        logger.info(f'Healthcheck tx result: {res}')
    except TransactionError as e:
        logger.exception(f'Healthcheck failed: {e}')


def handle_healthcheck_job(
    scheduler: BackgroundScheduler,
    node_config: NodeConfig,
) -> None:
    job = scheduler.get_job(BACKGROUND_JOB_NAME)
    if job is None:
        logger.info('Adding healthcheck job to the scheduler')
        local_mirage = init_local_mirage(node_config)
        heartbeat_interval = local_mirage.status.heartbeat_interval()
        safe_heartbeat_interval = heartbeat_interval - INTERVAL_BUFFER
        logger.info(f'Healthcheck job will run every {heartbeat_interval} seconds')
        scheduler.add_job(
            func=healthcheck_job,
            args=[local_mirage],
            trigger='interval',
            seconds=safe_heartbeat_interval,
            id=BACKGROUND_JOB_NAME,
            name='Mirage Healthcheck Job',
        )
        scheduler.start()
        logger.info('Healthcheck scheduler started - jobs will now execute')
    else:
        logger.info('Healthcheck job already exists in the scheduler, skipping')
