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
from concurrent.futures import Future, ThreadPoolExecutor
from importlib import reload
from typing import List, Optional

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
from core.schains.task import keep_tasks_running, Task
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.rotation import get_schain_public_key
from core.schains.skaled_status import get_skaled_status
from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.ima import DISABLE_IMA
from tools.helper import is_node_part_of_chain
from web.models.schain import upsert_schain_record


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 1
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 9

SKALED_PIPELINE_SLEEP = 10
CONFIG_PIPELINE_SLEEP = 40

logger = logging.getLogger(__name__)


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


def post_monitor_sleep():
    schain_monitor_sleep = random.randint(
        MIN_SCHAIN_MONITOR_SLEEP_INTERVAL,
        MAX_SCHAIN_MONITOR_SLEEP_INTERVAL
    )
    logger.info('Monitor completed, sleeping for %d', schain_monitor_sleep)
    time.sleep(schain_monitor_sleep)


def create_and_execute_tasks(
    skale,
    schain,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    stream_version,
    executor,
    futures,
    dutils
):
    reload(web3_request)
    name = schain['name']

    is_rotation_active = skale.node_rotation.is_rotation_active(name)

    leaving_chain = not is_node_part_of_chain(skale, name, node_config.id)
    if leaving_chain and not is_rotation_active:
        logger.warning('NOT ON NODE ({node_config.id}), finising process...')
        return True

    tasks = [
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
            sleep=SKALED_PIPELINE_SLEEP
        )
    ]
    if not leaving_chain:
        tasks.append(
            Task(
                f'{name}-config',
                functools.partial(
                    run_config_pipeline,
                    skale=skale,
                    schain=schain,
                    node_config=node_config,
                    stream_version=stream_version
                ),
                sleep=CONFIG_PIPELINE_SLEEP
            ))

    keep_tasks_running(executor, tasks, futures)


def run_monitor_for_schain(
    skale,
    skale_ima,
    node_config: NodeConfig,
    schain,
    dutils=None,
    once=False
):
    stream_version = get_skale_node_version()

    tasks_number = 2
    with ThreadPoolExecutor(max_workers=tasks_number, thread_name_prefix='T') as executor:
        futures: List[Optional[Future]] = [None for i in range(tasks_number)]
        while True:
            try:
                create_and_execute_tasks(
                    skale,
                    schain,
                    node_config,
                    skale_ima,
                    stream_version,
                    executor,
                    futures,
                    dutils
                )
                if once:
                    return True
                post_monitor_sleep()
            except Exception:
                logger.exception('Monitor failed')
                if once:
                    return False
                post_monitor_sleep()
