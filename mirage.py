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

from skale import MirageManager
from filelock import FileLock

from core.node_config import NodeConfig
from core.mirage.process_manager import start_tasks
from core.monitoring import update_monitoring_services

from tools.configs import INIT_LOCK_PATH
from tools.configs.web3 import ENDPOINT, MIRAGE_CONTRACTS
from tools.logger import init_admin_logger
from tools.sgx_utils import generate_sgx_key
from tools.wallet_utils import init_wallet

init_admin_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 90


def monitor(mirage: MirageManager, node_config: NodeConfig) -> None:
    while True:
        try:
            start_tasks(mirage, node_config)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(SLEEP_INTERVAL)


def worker() -> None:
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    if MIRAGE_CONTRACTS is None:
        logger.error('MIRAGE_CONTRACTS is not set. Exiting.')
        return

    wallet = init_wallet(node_config=node_config)
    mirage = MirageManager(ENDPOINT, MIRAGE_CONTRACTS, wallet)

    update_monitoring_services(node_config.ip, node_config.id, mirage.committee.address)
    monitor(mirage, node_config)


def main():
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        generate_sgx_key(node_config)
    worker()


if __name__ == '__main__':
    main()
