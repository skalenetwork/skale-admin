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
import logging
import queue
import random
import sys
import threading
import time
from typing import Callable, Dict, List, NamedTuple, Optional
from concurrent.futures import Future, ThreadPoolExecutor
from importlib import reload

from skale import Skale, SkaleIma
from web3._utils import request as web3_request

from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.schains.checks import ConfigChecks, get_api_checks_status, TG_ALLOWED_CHECKS, SkaledChecks
from core.schains.config.file_manager import ConfigFileManager
from core.schains.firewall import get_default_rule_controller
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.monitor import get_skaled_monitor, RegularConfigMonitor, SyncConfigMonitor
from core.schains.monitor.action import ConfigActionManager, SkaledActionManager
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.task import keep_tasks_running, Task
from core.schains.config.static_params import get_automatic_repair_option
from core.schains.skaled_status import get_skaled_status
from core.node import get_current_nodes

from tools.docker_utils import DockerUtils
from tools.configs import SYNC_NODE
from tools.notifications.messages import notify_checks
from tools.helper import is_node_part_of_chain, no_hyphens
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 20
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 40

SKALED_PIPELINE_SLEEP = 2
CONFIG_PIPELINE_SLEEP = 3
STUCK_TIMEOUT = 60 * 60 * 3
SHUTDOWN_INTERVAL = 60 * 10

logger = logging.getLogger(__name__)


class Pipeline(NamedTuple):
    name: str
    job: Callable


def run_config_pipeline(
    skale: Skale, skale_ima: SkaleIma, schain: Dict, node_config: NodeConfig, stream_version: str
) -> None:
    name = schain['name']
    schain_record = SChainRecord.get_by_name(name)
    rotation_data = skale.node_rotation.get_rotation(name)
    allowed_ranges = get_sync_agent_ranges(skale)
    ima_linked = not SYNC_NODE and skale_ima.linker.has_schain(name)
    group_index = skale.schains.name_to_group_id(name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(group_index)
    current_nodes = get_current_nodes(skale, name)

    estate = ExternalState(
        ima_linked=ima_linked, chain_id=skale_ima.web3.eth.chain_id, ranges=allowed_ranges
    )
    econfig = ExternalConfig(name)
    config_checks = ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data['rotation_id'],
        current_nodes=current_nodes,
        last_dkg_successful=last_dkg_successful,
        econfig=econfig,
        estate=estate,
    )

    config_am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=stream_version,
        checks=config_checks,
        current_nodes=current_nodes,
        estate=estate,
        econfig=econfig,
    )

    status = config_checks.get_all(log=False, expose=True)
    logger.info('Config checks: %s', status)

    if SYNC_NODE:
        logger.info(
            'Sync node last_dkg_successful %s, rotation_data %s', last_dkg_successful, rotation_data
        )
        mon = SyncConfigMonitor(config_am, config_checks)
    else:
        logger.info('Regular node mode, running config monitor')
        mon = RegularConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(name)}', rotation_data['rotation_id']
    )
    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(name)}'):
        mon.run()


def run_skaled_pipeline(
    skale: Skale, schain: Dict, node_config: NodeConfig, dutils: DockerUtils
) -> None:
    name = schain['name']
    schain_record = SChainRecord.get_by_name(name)
    logger.info('Record: %s', SChainRecord.to_dict(schain_record))

    dutils = dutils or DockerUtils()

    rc = get_default_rule_controller(name=name)
    skaled_checks = SkaledChecks(
        schain_name=schain['name'],
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )

    skaled_status = get_skaled_status(name)

    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        econfig=ExternalConfig(name),
        dutils=dutils,
    )
    check_status = skaled_checks.get_all(log=False, expose=True)
    automatic_repair = get_automatic_repair_option()
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(name, node_config.all(), api_status)

    logger.info('Skaled check status: %s', check_status)

    logger.info('Upstream config %s', skaled_am.upstream_config_path)

    mon = get_skaled_monitor(
        action_manager=skaled_am,
        check_status=check_status,
        schain_record=schain_record,
        skaled_status=skaled_status,
        automatic_repair=automatic_repair,
    )

    statsd_client = get_statsd_client()
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(name)}'):
        mon(skaled_am, skaled_checks).run()


def post_monitor_sleep():
    schain_monitor_sleep = random.randint(
        MIN_SCHAIN_MONITOR_SLEEP_INTERVAL, MAX_SCHAIN_MONITOR_SLEEP_INTERVAL
    )
    logger.info('Monitor iteration completed, sleeping for %d', schain_monitor_sleep)
    time.sleep(schain_monitor_sleep)


def create_and_execute_tasks(
    skale,
    schain,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    stream_version,
    schain_record,
    executor,
    futures,
    dutils,
):
    reload(web3_request)
    name = schain['name']

    is_rotation_active = skale.node_rotation.is_rotation_active(name)

    leaving_chain = not SYNC_NODE and not is_node_part_of_chain(skale, name, node_config.id)
    if leaving_chain and not is_rotation_active:
        logger.info('Not on node (%d), finishing process', node_config.id)
        return True

    logger.info(
        'sync_config_run %s, config_version %s, stream_version %s',
        schain_record.sync_config_run,
        schain_record.config_version,
        stream_version,
    )

    statsd_client = get_statsd_client()
    monitor_last_seen_ts = schain_record.monitor_last_seen.timestamp()
    statsd_client.incr(f'admin.schain.monitor.{no_hyphens(name)}')
    statsd_client.gauge(f'admin.schain.monitor_last_seen.{no_hyphens(name)}', monitor_last_seen_ts)

    tasks = []
    if not leaving_chain:
        logger.info('Adding config task to the pool')
        tasks.append(
            Task(
                f'{name}-config',
                functools.partial(
                    run_config_pipeline,
                    skale=skale,
                    skale_ima=skale_ima,
                    schain=schain,
                    node_config=node_config,
                    stream_version=stream_version,
                ),
                sleep=CONFIG_PIPELINE_SLEEP,
            )
        )
    if schain_record.config_version != stream_version or (
        schain_record.sync_config_run and schain_record.first_run
    ):
        ConfigFileManager(name).remove_skaled_config()
    else:
        logger.info('Adding skaled task to the pool')
        tasks.append(
            Task(
                f'{name}-skaled',
                functools.partial(
                    run_skaled_pipeline,
                    skale=skale,
                    schain=schain,
                    node_config=node_config,
                    dutils=dutils,
                ),
                sleep=SKALED_PIPELINE_SLEEP,
            )
        )

    if len(tasks) == 0:
        logger.warning('No tasks to run')
    keep_tasks_running(executor, tasks, futures)


def run_monitor_for_schain(
    skale, skale_ima, node_config: NodeConfig, schain, dutils=None, once=False
):
    stream_version = get_skale_node_version()
    tasks_number = 2
    with ThreadPoolExecutor(max_workers=tasks_number, thread_name_prefix='T') as executor:
        futures: List[Optional[Future]] = [None for i in range(tasks_number)]
        while True:
            schain_record = SChainRecord.get_by_name(schain['name'])
            try:
                create_and_execute_tasks(
                    skale,
                    schain,
                    node_config,
                    skale_ima,
                    stream_version,
                    schain_record,
                    executor,
                    futures,
                    dutils,
                )
                if once:
                    return True
                post_monitor_sleep()
            except Exception:
                logger.exception('Monitor iteration failed')
                if once:
                    return False
                post_monitor_sleep()


def run_pipelines(
    pipelines: list[Pipeline],
    once: bool = False,
    stuck_timeout: int = STUCK_TIMEOUT,
    shutdown_interval: int = SHUTDOWN_INTERVAL,
) -> None:
    init_ts = time.time()

    heartbeat_queues = [queue.Queue() for _ in range(len(pipelines))]
    terminating_events = [threading.Event() for _ in range(len(pipelines))]
    heartbeat_ts = [init_ts for _ in range(len(pipelines))]

    threads = [
        threading.Thread(
            name=pipeline.name,
            target=keep_pipeline, args=[heartbeat_queue, terminating_event, pipeline.job],
            daemon=True
        )
        for heartbeat_queue, terminating_event, pipeline in zip(
            heartbeat_queues, terminating_events, pipelines
        )
    ]

    for th in threads:
        th.start()

    stuck = False
    while not stuck:
        for pindex, heartbeat_queue in enumerate(heartbeat_queues):
            if not heartbeat_queue.empty():
                heartbeat_ts[pindex] = heartbeat_queue.get()
            if time.time() - heartbeat_ts[pindex] > stuck_timeout:
                logger.info('Pipeline with number %d/%d stuck', pindex, len(pipelines))
                stuck = True
                break
        if once and all((lambda ts: ts > init_ts, heartbeat_ts)):
            logger.info('Successfully completed required one run. Shutting down the process')
            break

    logger.info('Terminating all pipelines')
    for event in terminating_events:
        event.set()
    if stuck:
        logger.info('Waiting for graceful completion interval')
        time.sleep(shutdown_interval)
        logger.info('Stuck was detected')
        sys.exit(1)


def keep_pipeline(
    heartbeat_queue: queue.Queue, terminating_event: threading.Event, pipeline: Callable
) -> None:
    while not terminating_event.is_set():
        logger.info('Running pipeline')
        pipeline()
        heartbeat_queue.put(time.time())
        post_monitor_sleep()
