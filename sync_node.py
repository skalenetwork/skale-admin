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

import os
import time
import logging
from typing import Dict

from skale import Skale, SkaleIma
from skale.schain_config.ports_allocation import get_schain_base_port_on_node

from core.schains.process_manager import run_pm_schain
from core.node_config import NodeConfig
from core.ima.schain import update_predeployed_ima

from tools.node_options import NodeOptions
from tools.logger import init_sync_logger
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH
from tools.configs.ima import MAINNET_IMA_ABI_FILEPATH

from web.models.schain import create_tables
from web.migrations import migrate


init_sync_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 180
WORKER_RESTART_SLEEP_INTERVAL = 2

SCHAIN_NAME = os.environ.get('SCHAIN_NAME')


def monitor(skale, skale_ima, node_config, schain: Dict) -> None:
    while True:
        try:
            run_pm_schain(skale, skale_ima, node_config, schain)
        except Exception:
            logger.exception('Process manager procedure failed!')
        logger.info(
            f'Sleeping for {SLEEP_INTERVAL}s after run_process_manager'
        )
        time.sleep(SLEEP_INTERVAL)


def worker(schain_name: str):
    skale = Skale(ENDPOINT, ABI_FILEPATH)
    skale_ima = SkaleIma(ENDPOINT, MAINNET_IMA_ABI_FILEPATH)

    if not skale.schains_internal.is_schain_exist(schain_name):
        logger.error(f'Provided SKALE Chain does not exist: {schain_name}')
        exit(1)

    schain = skale.schains.get_by_name(schain_name)
    node_config = NodeConfig()
    node_options = NodeOptions()

    schain_nodes = skale.schains_internal.get_node_ids_for_schain(schain_name)
    if not node_config.id:
        node_config.id = schain_nodes[0]

    node = skale.nodes.get(node_config.id)
    if node_options.schain_base_port == -1:
        node_options.schain_base_port = get_schain_base_port_on_node(
            schain_nodes,
            schain_name,
            node['port']
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
            update_predeployed_ima()
            worker(SCHAIN_NAME)
        except Exception:
            logger.exception('Sync node worker failed')
        time.sleep(WORKER_RESTART_SLEEP_INTERVAL)


if __name__ == '__main__':
    main()
