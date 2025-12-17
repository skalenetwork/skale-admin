#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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
from multiprocessing import Process
from typing import Optional

from skale import SkaleIma, SkaleManager
from skale.types.schain import SchainStructure

from core.cache import AdminCache
from core.monitor.schain.main import start_tasks
from core.node_config import NodeConfig
from core.schains.notifications import notify_if_not_enough_balance
from core.schains.process import (
    get_schain_process_info,
    is_monitor_process_alive,
    terminate_process,
)
from tools.configs import PASSIVE_NODE
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from tools.helper import is_node_part_of_chain

logger = logging.getLogger(__name__)


def run_process_manager(
    skale: SkaleManager, skale_ima: SkaleIma, node_config: NodeConfig, admin_cache: AdminCache
) -> None:
    logger.info('Process manager started')
    node_info = node_config.all()
    notify_if_not_enough_balance(skale, node_info)
    for schain in admin_cache.schains:
        run_pm_schain(skale, skale_ima, node_config, schain, admin_cache)
    logger.info('Process manager procedure finished')


def run_pm_schain(
    skale: SkaleManager,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    schain: SchainStructure,
    admin_cache: AdminCache,
    timeout: Optional[int] = None,
) -> None:
    log_prefix = f'sChain {schain.name} -'

    if timeout is not None:
        allowed_diff = timeout
    else:
        dkg_timeout = admin_cache.dkg_timeout
        allowed_diff = timeout or int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    is_rotation_active = skale.node_rotation.is_rotation_active(schain.name)
    leaving_chain = not PASSIVE_NODE and not is_node_part_of_chain(
        skale, schain.name, node_config.id
    )
    if leaving_chain and not is_rotation_active:
        logger.info('Not on node (%d), skipping', node_config.id)
        return

    pid, pts = get_schain_process_info(schain.name)
    if pid is not None and is_monitor_process_alive(pid):
        if int(time.time()) - pts > allowed_diff:
            logger.info('%s Terminating process: PID = %d', log_prefix, pid)
            terminate_process(pid)
        else:
            logger.info('%s Process is running: PID = %d', log_prefix, pid)
    else:
        process = Process(
            name=schain.name, target=start_tasks, args=(schain, node_config, skale_ima, admin_cache)
        )
        process.start()
        logger.info('Process started for %s', schain.name)
