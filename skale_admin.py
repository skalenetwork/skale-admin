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
from skale.schain_config.ports_allocation import get_schain_base_port_on_node
from skale.types.schain import SchainName, SchainStructure
from skale.utils.helper import schain_name_to_hash
from skale_core.settings import (
    SkalePassiveSettings,
    SkaleSettings,
    get_internal_settings,
    get_settings,
)

import tools.settings  # noqa: F401
from core.ima.abi import generate_ima_container_abis
from core.manager_cache import ManagerCache
from core.monitoring import update_monitoring_services
from core.node_config import NodeConfig
from core.redis.migrations import run_redis_migrations
from core.schains.cleaner import run_cleaner
from core.schains.process import cleanup_schains_pids
from core.schains.process_manager import run_pm_schain, run_process_manager
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

ACTIVE_SLEEP_INTERVAL = 240
PASSIVE_SLEEP_INTERVAL = 360
WORKER_RESTART_SLEEP_INTERVAL = 2


def init_db() -> None:
    create_tables()
    migrate()


def monitor_active(skale: SkaleManager, skale_ima: SkaleIma, node_config: NodeConfig) -> None:
    manager_cache: ManagerCache = ManagerCache(rs, skale, node_config.id)
    manager_cache.clear_all_fields()
    while True:
        try:
            run_process_manager(skale, skale_ima, node_config, manager_cache)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {ACTIVE_SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(ACTIVE_SLEEP_INTERVAL)
        try:
            run_cleaner(skale, node_config, manager_cache)
        except Exception:
            logger.exception('Cleaner procedure failed!')
        logger.info(f'Sleeping for {ACTIVE_SLEEP_INTERVAL}s after run_cleaner')
        time.sleep(ACTIVE_SLEEP_INTERVAL)


def monitor_passive(
    skale: SkaleManager, skale_ima: SkaleIma, node_config: NodeConfig, schain: SchainStructure
) -> None:
    manager_cache = ManagerCache(rs, skale, node_config.id)
    while True:
        try:
            run_pm_schain(skale, skale_ima, node_config, schain, manager_cache)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {PASSIVE_SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(PASSIVE_SLEEP_INTERVAL)


def worker_active() -> None:
    node_config = NodeConfig()
    st = get_settings(SkaleSettings)
    internal_st = get_internal_settings()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(ACTIVE_SLEEP_INTERVAL)
    wallet = init_wallet(
        node_config=node_config, endpoint=str(st.endpoint), sgx_server_url=str(st.sgx_url)
    )
    skale = SkaleManager(str(st.endpoint), st.manager_contracts, wallet)
    skale_ima = SkaleIma(str(st.endpoint), st.ima_contracts, wallet)
    if internal_st.backup_run:
        logger.info('Running sChains in snapshot download mode')
    update_monitoring_services(node_config.ip, node_config.id, skale.manager.address)
    monitor_active(skale, skale_ima, node_config)


def worker_passive(schain_name: SchainName) -> None:
    st = get_settings(SkalePassiveSettings)
    skale = SkaleManager(str(st.endpoint), st.manager_contracts)
    skale_ima = SkaleIma(str(st.endpoint), st.ima_contracts)

    if not skale.schains_internal.is_schain_exist(schain_name):
        logger.error(f'Provided SKALE Chain does not exist: {schain_name}')
        exit(1)

    schain = skale.schains.get_by_name(schain_name)
    node_config = NodeConfig()

    schain_nodes = skale.schains_internal.node_ids_for_schain(schain_name)
    if not node_config.id:
        node_config.id = schain_nodes[0]

    node = skale.nodes.get(node_config.id)
    schain_hash = schain_name_to_hash(schain_name)
    if node_config.schain_base_port == -1:
        schain_hashes = skale.schains_internal.get_schain_hashes_for_node(node_config.id)
        node_config.schain_base_port = get_schain_base_port_on_node(
            schain_hashes, schain_hash, node['port']
        )

    logger.info(f'Node {node_config.id} will be used as a current node')
    monitor_passive(skale, skale_ima, node_config, schain)


def init_active() -> None:
    st = get_settings(SkaleSettings)
    internal_st = get_internal_settings()
    skale = SkaleManager(str(st.endpoint), st.manager_contracts)
    node_config = NodeConfig()
    init_lock = FileLock(INIT_LOCK_PATH)
    with init_lock:
        generate_sgx_key(node_config)
        update_node_config_file(skale, node_config)
        init_db()
        run_redis_migrations()
        set_schains_first_run()
        cleanup_schains_pids()
        if internal_st.backup_run:
            set_schains_backup_run()
        if internal_st.pull_config_for_schain:
            set_schains_sync_config_run(internal_st.pull_config_for_schain)
        cleanup_notification_state()
        generate_ima_container_abis(skale, SkaleIma(str(st.endpoint), st.ima_contracts))


def run_active() -> None:
    logger.info('Starting active node worker')
    while True:
        try:
            init_active()
            worker_active()
        except Exception:
            logger.exception('Admin worker failed')
        time.sleep(WORKER_RESTART_SLEEP_INTERVAL)


def run_passive() -> None:
    logger.info('Starting passive node worker')
    st = get_settings(SkalePassiveSettings)
    while True:
        try:
            init_db()
            worker_passive(st.schain_name)
        except Exception:
            logger.exception('Sync node worker failed')
        time.sleep(WORKER_RESTART_SLEEP_INTERVAL)


def main() -> None:
    internal_st = get_internal_settings()
    if internal_st.node_mode == 'passive':
        run_passive()
    else:
        run_active()


if __name__ == '__main__':
    main()
