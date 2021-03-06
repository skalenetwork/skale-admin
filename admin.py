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

from core.node_config import NodeConfig
from core.schains.creator import run_creator
from core.schains.cleaner import run_cleaner
from core.updates import soft_updates

from tools.configs import BACKUP_RUN
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH
from tools.logger import init_admin_logger
from tools.notifications.messages import cleanup_notification_state
from tools.wallet_utils import init_wallet

from web.models.schain import set_schains_first_run
from web.migrations import run_migrations


init_admin_logger()
logger = logging.getLogger(__name__)

INITIAL_SLEEP_INTERVAL = 135
SLEEP_INTERVAL = 50
MONITOR_INTERVAL = 45


def monitor(skale, node_config):
    while True:
        run_creator(skale, node_config)
        time.sleep(MONITOR_INTERVAL)
        run_cleaner(skale, node_config)
        time.sleep(MONITOR_INTERVAL)


def main():
    time.sleep(INITIAL_SLEEP_INTERVAL)
    node_config = NodeConfig()
    while node_config.id is None:
        logger.info('Waiting for the node_id ...')
        time.sleep(SLEEP_INTERVAL)

    wallet = init_wallet(node_config, retry_if_failed=True)
    skale = Skale(ENDPOINT, ABI_FILEPATH, wallet)

    soft_updates(skale, node_config)
    run_migrations()

    set_schains_first_run()
    cleanup_notification_state()
    if BACKUP_RUN:
        logger.info('Running sChains in snapshot download mode')
    monitor(skale, node_config)


if __name__ == '__main__':
    main()
