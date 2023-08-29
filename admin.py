#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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

from skale import Skale, SkaleIma
from filelock import FileLock

from core.node_config import NodeConfig
from core.schains.process_manager import run_process_manager
from core.schains.cleaner import run_cleaner
from core.updates import soft_updates
from core.filebeat import update_filebeat_service

from tools.configs import BACKUP_RUN, INIT_LOCK_PATH, PULL_CONFIG_FOR_SCHAIN
from tools.configs.web3 import (
    ENDPOINT, ABI_FILEPATH, STATE_FILEPATH)
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH
from tools.logger import init_admin_logger
from tools.notifications.messages import cleanup_notification_state
from tools.sgx_utils import generate_sgx_key
from tools.wallet_utils import init_wallet

from web.models.schain import (
    create_tables,
    set_schains_backup_run,
    set_schains_first_run,
    set_schains_monitor_id,
    set_schains_sync_config_run
)
from web.migrations import migrate


init_admin_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 90
WORKER_RESTART_SLEEP_INTERVAL = 2
ERROR_SLEEP_INTERVAL = 1


def monitor(skale, skale_ima, node_config):
    while True:
        try:
            run_process_manager(skale, skale_ima, node_config)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(
            f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager'
        )
        time.sleep(SLEEP_INTERVAL)
        run_cleaner(skale, node_config)
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_cleaner')
        time.sleep(SLEEP_INTERVAL)


def worker():
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    wallet = init_wallet(node_config=node_config)
    skale = Skale(ENDPOINT, ABI_FILEPATH, wallet, state_path=STATE_FILEPATH)
    skale_ima = SkaleIma(ENDPOINT, MAINNET_IMA_ABI_FILEPATH, wallet)
    if BACKUP_RUN:
        logger.info('Running sChains in snapshot download mode')
    update_filebeat_service(node_config.ip, node_config.id, skale)
    monitor(skale, skale_ima, node_config)


def init():
    skale = Skale(ENDPOINT, ABI_FILEPATH, state_path=STATE_FILEPATH)
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        generate_sgx_key(node_config)
        soft_updates(skale, node_config)
        create_tables()
        migrate()
        set_schains_first_run()
        set_schains_monitor_id()
        if BACKUP_RUN:
            set_schains_backup_run()
        if PULL_CONFIG_FOR_SCHAIN:
            set_schains_sync_config_run(PULL_CONFIG_FOR_SCHAIN)
        cleanup_notification_state()


def main():
    try:
        init()
        while True:
            worker()
            time.sleep(WORKER_RESTART_SLEEP_INTERVAL)
    except Exception:
        logger.exception('Admin worker failed')
        time.sleep(ERROR_SLEEP_INTERVAL)


if __name__ == '__main__':
    main()
