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

from skale import Skale
from skale.wallets import RPCWallet

from core.node_config import NodeConfig
from core.schains.creator import run_creator
from core.schains.cleaner import run_cleaner

from tools.configs import BACKUP_RUN
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH, TM_URL
from tools.logger import init_admin_logger

from web.models.schain import SChainRecord


init_admin_logger()
logger = logging.getLogger(__name__)

SLEEP_INTERVAL = 50
MONITOR_INTERVAL = 45


def set_schains_first_run():
    logger.info('Setting first_run=True for all sChain records')
    query = SChainRecord.update(first_run=True).where(
        SChainRecord.first_run == False)  # noqa
    query.execute()


def monitor(skale, node_config):
    while True:
        run_creator(skale, node_config)
        time.sleep(MONITOR_INTERVAL)
        run_cleaner(skale, node_config)
        time.sleep(MONITOR_INTERVAL)


def main():
    rpc_wallet = RPCWallet(TM_URL)
    skale = Skale(ENDPOINT, ABI_FILEPATH, rpc_wallet)
    node_config = NodeConfig()
    set_schains_first_run()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)
    if BACKUP_RUN:
        logger.info('Running sChains in snapshot download mode')
    monitor(skale, node_config)


if __name__ == '__main__':
    main()
