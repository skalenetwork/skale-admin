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

import functools
import time
import random
import logging
from typing import Dict
from importlib import reload

from skale import Skale, SkaleIma
from web3._utils import request as web3_request

from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.schains.checks import ConfigChecks, SkaledChecks
from core.schains.firewall import get_default_rule_controller
from core.schains.ima import ImaData
from core.schains.monitor import (
    get_skaled_monitor,
    RegularConfigMonitor
)
from core.schains.monitor.action import ConfigActionManager, SkaledActionManager
from core.schains.task import run_tasks, Task
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.rotation import get_schain_public_key
from core.schains.skaled_status import get_skaled_status
from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.ima import DISABLE_IMA
from tools.helper import is_node_part_of_chain
from web.models.schain import upsert_schain_record


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 90
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 180


logger = logging.getLogger(__name__)


def get_log_prefix(name):
    return f'schain: {name} -'


def run_config_pipeline(
    skale: Skale,
    schain: Dict,
    node_config: NodeConfig,
    stream_version: str
) -> None:
    name = schain['name']
    schain_record = upsert_schain_record(name)
    rotation_data = skale.node_rotation.get_rotation(name)
    config_checks = ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data['rotation_id']
    )

    config_am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=stream_version,
        checks=config_checks
    )

    mon = RegularConfigMonitor(config_am, config_checks)
    mon.run()


def run_skaled_pipeline(
    skale: Skale,
    skale_ima: SkaleIma,
    schain: Dict,
    node_config: NodeConfig,
    dutils: DockerUtils
) -> None:
    name = schain['name']
    schain_record = upsert_schain_record(name)

    dutils = dutils or DockerUtils()

    ima_linked = not DISABLE_IMA and skale_ima.linker.has_schain(name)

    sync_agent_ranges = get_sync_agent_ranges(skale)

    rc = get_default_rule_controller(
        name=name,
        sync_agent_ranges=sync_agent_ranges
    )
    skaled_checks = SkaledChecks(
        schain_name=schain['name'],
        schain_record=schain_record,
        rule_controller=rc,
        ima_linked=ima_linked,
        dutils=dutils
    )

    ima_data = ImaData(
        linked=ima_linked,
        chain_id=skale_ima.web3.eth.chain_id
    )

    skaled_status = get_skaled_status(name)

    public_key = get_schain_public_key(skale, name)

    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        ima_data=ima_data,
        checks=skaled_checks,
        node_config=node_config,
        public_key=public_key,
        dutils=dutils
    )
    mon = get_skaled_monitor(
        action_manager=skaled_am,
        checks=skaled_checks,
        schain_record=schain_record,
        skaled_status=skaled_status,
        backup_run=BACKUP_RUN
    )
    mon.run()


def run_monitor_for_schain(
    skale,
    skale_ima,
    node_config: NodeConfig,
    schain,
    dutils=None,
    once=False
):
    p = get_log_prefix(schain['name'])
    stream_version = get_skale_node_version()

    def post_monitor_sleep():
        schain_monitor_sleep = random.randint(
            MIN_SCHAIN_MONITOR_SLEEP_INTERVAL,
            MAX_SCHAIN_MONITOR_SLEEP_INTERVAL
        )
        logger.info('%s monitor completed, sleeping for {schain_monitor_sleep}s...', p)
        time.sleep(schain_monitor_sleep)

    while True:
        try:
            reload(web3_request)
            name = schain['name']

            is_rotation_active = skale.node_rotation.is_rotation_active(name)

            if not is_node_part_of_chain(skale, name, node_config.id) and not is_rotation_active:
                logger.warning(f'{p} NOT ON NODE ({node_config.id}), finising process...')
                return True

            tasks = [
                Task(
                    f'{name}-config',
                    functools.partial(
                        run_config_pipeline,
                        skale=skale,
                        schain=schain,
                        node_config=node_config,
                        stream_version=stream_version
                    )
                ),
                Task(
                    f'{name}-skaled',
                    functools.partial(
                        run_skaled_pipeline,
                        skale=skale,
                        skale_ima=skale_ima,
                        schain=schain,
                        node_config=node_config,
                        dutils=dutils
                    ),
                )
            ]
            run_tasks(name=name, tasks=tasks)
            if once:
                return True
            post_monitor_sleep()
        except Exception:
            logger.exception('%s monitor failed', p)
            if once:
                return False
            post_monitor_sleep()
