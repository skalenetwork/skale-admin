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
import queue
import threading
import time
from multiprocessing import Process
from typing import Optional

from skale import Skale, SkaleIma

from core.node_config import NodeConfig
from core.schains.monitor.main import get_pipelines, start_monitor
from core.schains.monitor.pipeline import keep_pipeline
from core.schains.process import (
    is_monitor_process_alive,
    terminate_process,
    ProcessReport,
)

from tools.str_formatters import arguments_list_string
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT

logger = logging.getLogger(__name__)


def run_pipelines(
    threads: list[threading.Thread],
    heartbeat_queues: list[queue.Queue],
    once: bool = False,
) -> bool:
    stuck_timeout = 10
    init_ts = int(time.time())
    heartbeat_ts = [init_ts for _ in range(len(threads))]

    for index, thread in enumerate(threads):
        if not thread.is_alive():
            thread.start()
        if not heartbeat_queues[index].empty():
            heartbeat_ts[index] = heartbeat_queues[index].get()
        ts = int(time.time())
        if ts - heartbeat_ts[index] > stuck_timeout:
            logger.warning(
                '%s thread has stucked (last heartbeat %d)',
                thread.name,
                heartbeat_ts[index],
            )
            return True
        if once and all((lambda ts: ts > init_ts, heartbeat_ts)):
            logger.info('Successfully completed requested single run')
            return False


def run_process_manager(skale: Skale, node_config: NodeConfig) -> None:
    logger.info('Process manager started')
    node_id = node_config.id

    schains_to_monitor = fetch_schains_to_monitor(skale, node_id)

    pipelines = []
    for schain in schains_to_monitor:
        pipelines.extend(get_pipelines(schain, node_config))

    heartbeat_queues = [queue.Queue() for _ in range(len(pipelines))]
    terminating_events = [threading.Event() for _ in range(len(pipelines))]

    threads = [
        Process(
            name=pipeline.name,
            target=keep_pipeline,
            args=[heartbeat_queue, terminating_event, pipeline.job],
        )
        for heartbeat_queue, terminating_event, pipeline in zip(
            heartbeat_queues, terminating_events, pipelines
        )
    ]
    stuck = run_pipelines(threads, heartbeat_queues)

    logger.info('Terminating all pipelines')
    for event in terminating_events:
        if not event.is_set():
            event.set()

    shutdown_interval = 10
    logger.info('Joining threads with timeout')
    for thread in threads:
        thread.join(timeout=shutdown_interval)
    if stuck:
        logger.info('Stuck was detected')

    logger.info('Finishing with pipelines')


def run_pm_schain(
    skale: Skale,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    schain: dict,
    timeout: Optional[int] = None,
) -> None:
    log_prefix = f'sChain {schain["name"]} -'

    if timeout is not None:
        allowed_diff = timeout
    else:
        dkg_timeout = skale.constants_holder.get_dkg_timeout()
        allowed_diff = timeout or int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    process_report = ProcessReport(schain['name'])
    init_ts = int(time.time())
    if process_report.is_exist():
        if init_ts - process_report.ts > allowed_diff:
            logger.info('%s Terminating process: PID = %d', log_prefix, process_report.pid)
            terminate_process(process_report.pid)
        else:
            pid = process_report.pid
            logger.info('%s Process is running: PID = %d', log_prefix, pid)

    if not process_report.is_exist() or not is_monitor_process_alive(process_report.pid):
        process_report.ts = init_ts
        process = Process(
            name=schain['name'],
            target=start_monitor,
            args=(skale, schain, node_config, skale_ima, process_report),
        )
        process.start()
        pid = process.ident
        process_report.pid = pid
        logger.info('%s Process started: PID = %d', log_prefix, pid)


def fetch_schains_to_monitor(skale: Skale, node_id: int) -> list:
    """
    Returns list of sChain dicts that admin should monitor (currently assigned + rotating).
    """
    logger.info('Fetching schains to monitor...')
    schains = skale.schains.get_schains_for_node(node_id)
    leaving_schains = get_leaving_schains_for_node(skale, node_id)
    schains.extend(leaving_schains)
    active_schains = list(filter(lambda schain: schain['active'], schains))
    schains_holes = len(schains) - len(active_schains)
    logger.info(
        arguments_list_string(
            {
                'Node ID': node_id,
                'sChains on node': active_schains,
                'Number of sChains on node': len(active_schains),
                'Empty sChain structs': schains_holes,
            },
            'Monitoring sChains',
        )
    )
    return active_schains


def get_leaving_schains_for_node(skale: Skale, node_id: int) -> list:
    logger.info('Get leaving_history for node ...')
    leaving_schains = []
    leaving_history = skale.node_rotation.get_leaving_history(node_id)
    for leaving_schain in leaving_history:
        schain = skale.schains.get(leaving_schain['schain_id'])
        if skale.node_rotation.is_rotation_active(schain['name']) and schain['name']:
            schain['active'] = True
            leaving_schains.append(schain)
    logger.info(f'Got leaving sChains for the node: {leaving_schains}')
    return leaving_schains
