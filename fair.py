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
import time

from apscheduler.schedulers.background import BackgroundScheduler
from filelock import FileLock

from core.config.schain.static_params import get_fair_chain_name
from core.monitor.fair.main import start_tasks
from core.monitoring import update_monitoring_services
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.redis.migrations import run_redis_migrations
from tools.constants import INIT_LOCK_PATH
from tools.helper import is_passive
from tools.logger import init_fair_logger
from tools.settings import get_fair_base_settings, get_settings
from tools.sgx_utils import generate_sgx_key

init_fair_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 90


def monitor(node_config: NodeConfig) -> None:
    scheduler = BackgroundScheduler()
    scheduler.start()
    while True:
        try:
            start_tasks(node_config, scheduler=scheduler)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(SLEEP_INTERVAL)


def update_chain_record() -> None:
    logger.info('Updating chain record during fair admin startup')
    st = get_settings()
    chain_name = get_fair_chain_name(st.env_type)
    chain_record = ChainRecord(chain_name)
    chain_record.set_first_run(True)
    chain_record.set_restart_ts(0)


def worker() -> None:
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    st = get_fair_base_settings()
    update_monitoring_services(node_config.ip, node_config.id, st.contracts.fair)
    update_chain_record()
    monitor(node_config)


def main():
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        if not is_passive():
            generate_sgx_key(node_config)
        run_redis_migrations()
    worker()


if __name__ == '__main__':
    main()
