#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2022 SKALE Labs
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
import os
import time

from skale import SkaleIma, SkaleManager
from skale.schain_config.ports_allocation import get_schain_base_port_on_node
from skale.types.schain import SchainName, SchainStructure
from skale.utils.helper import schain_name_to_hash

from core.manager_cache import ManagerCache
from core.node_config import NodeConfig
from core.schains.process_manager import run_pm_schain
from tools.logger import init_sync_logger
from tools.resources import rs
from tools.settings import get_skale_base_settings
from web.migrations import migrate
from web.models.schain import create_tables

init_sync_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 360
WORKER_RESTART_SLEEP_INTERVAL = 2

SCHAIN_NAME = os.environ.get('SCHAIN_NAME')


def monitor(
    skale: SkaleManager, skale_ima: SkaleIma, node_config: NodeConfig, schain: SchainStructure
) -> None:
    manager_cache = ManagerCache(rs, skale, node_config.id)
    while True:
        try:
            run_pm_schain(skale, skale_ima, node_config, schain, manager_cache)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager')
        time.sleep(SLEEP_INTERVAL)


def worker(schain_name: SchainName):
    st = get_skale_base_settings()
    skale = SkaleManager(str(st.endpoint), st.contracts.manager)
    skale_ima = SkaleIma(str(st.endpoint), st.contracts.ima)

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
    monitor(skale, skale_ima, node_config, schain)


def main():
    if SCHAIN_NAME is None:
        raise Exception('You should provide SCHAIN_NAME')
    while True:
        try:
            create_tables()
            migrate()
            worker(SchainName(SCHAIN_NAME))
        except Exception:
            logger.exception('Sync node worker failed')
        time.sleep(WORKER_RESTART_SLEEP_INTERVAL)


if __name__ == '__main__':
    main()
