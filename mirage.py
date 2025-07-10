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

import time
import logging

from filelock import FileLock
from apscheduler.schedulers.background import BackgroundScheduler

from core.node_config import NodeConfig

from core.monitor.mirage.main import start_tasks
from core.redis.migrations import run_redis_migrations

from tools.configs import INIT_LOCK_PATH

from tools.logger import init_mirage_logger
from tools.sgx_utils import generate_sgx_key

init_mirage_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 90


def monitor(node_config: NodeConfig) -> None:
    scheduler = BackgroundScheduler()
    while True:
        try:
            start_tasks(node_config, scheduler=scheduler)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(SLEEP_INTERVAL)


def worker() -> None:
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    # TODOD: uncomment
    # update_monitoring_services(node_config.ip, node_config.id, mirage.committee.address)
    monitor(node_config)


def main():
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        generate_sgx_key(node_config)
        run_redis_migrations()
    worker()


if __name__ == '__main__':
    main()
