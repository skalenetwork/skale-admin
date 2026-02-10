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

from filelock import FileLock
from skale import SkaleIma, SkaleManager
from skale.core.settings import SkaleSettings, get_settings

from core.ima.abi import generate_ima_container_abis
from core.manager_cache import ManagerCache
from core.monitoring import update_monitoring_services
from core.node_config import NodeConfig
from core.redis.migrations import run_redis_migrations
from core.schains.cleaner import run_cleaner
from core.schains.process import cleanup_schains_pids
from core.schains.process_manager import run_process_manager
from core.updates import update_node_config_file
from tools.constants import INIT_LOCK_PATH
from tools.logger import init_admin_logger
from tools.notifications.messages import cleanup_notification_state
from tools.resources import rs
from tools.sgx_utils import generate_sgx_key
from tools.wallet_utils import init_wallet
from web.migrations import migrate
from web.models.schain import (
    create_tables,
    set_schains_backup_run,
    set_schains_first_run,
    set_schains_sync_config_run,
)

init_admin_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 240
WORKER_RESTART_SLEEP_INTERVAL = 2
ERROR_SLEEP_INTERVAL = 1


def monitor(skale: SkaleManager, skale_ima: SkaleIma, node_config: NodeConfig) -> None:
    manager_cache: ManagerCache = ManagerCache(rs, skale, node_config.id)
    manager_cache.clear_all_fields()
    while True:
        try:
            run_process_manager(skale, skale_ima, node_config, manager_cache)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(SLEEP_INTERVAL)
        run_cleaner(skale, node_config, manager_cache)
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_cleaner')
        time.sleep(SLEEP_INTERVAL)


def worker() -> None:
    node_config = NodeConfig()
    st = get_settings(SkaleSettings)
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)
    wallet = init_wallet(
        node_config=node_config, endpoint=str(st.endpoint), sgx_server_url=str(st.sgx_url)
    )
    skale = SkaleManager(str(st.endpoint), st.manager_contracts, wallet)
    skale_ima = SkaleIma(str(st.endpoint), st.ima_contracts, wallet)
    if st.backup_run:
        logger.info('Running sChains in snapshot download mode')
    update_monitoring_services(node_config.ip, node_config.id, skale.manager.address)
    monitor(skale, skale_ima, node_config)


def init() -> None:
    st = get_settings(SkaleSettings)
    skale = SkaleManager(str(st.endpoint), st.manager_contracts)
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        generate_sgx_key(node_config)
        update_node_config_file(skale, node_config)
        create_tables()
        migrate()
        run_redis_migrations()
        set_schains_first_run()
        cleanup_schains_pids()
        if st.backup_run:
            set_schains_backup_run()
        if st.pull_config_for_schain:
            set_schains_sync_config_run(st.pull_config_for_schain)
        cleanup_notification_state()
        generate_ima_container_abis(skale, SkaleIma(str(st.endpoint), st.ima_contracts))


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
