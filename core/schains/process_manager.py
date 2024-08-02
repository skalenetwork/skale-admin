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
import sys
import time
from typing import Dict
from multiprocessing import Process

from skale import Skale

from core.schains.monitor.main import create_and_execute_pipelines
from core.schains.notifications import notify_if_not_enough_balance
from core.schains.process import (
    is_monitor_process_alive,
    terminate_process,
    ProcessReport,
)

from web.models.schain import upsert_schain_record, SChainRecord
from tools.str_formatters import arguments_list_string


logger = logging.getLogger(__name__)


DKG_TIMEOUT_COEFFICIENT = 2.2


def pm_signal_handler(*args):
    """
    This function is trigerred when SIGTERM signal is received by the main process of the app.
    The purpose of the process manager signal handler is to forward SIGTERM signal to all sChain
    processes so they can gracefully save DKG results before
    """
    records = SChainRecord.select()
    print(f'schain_records: {len(records)}')
    print(f'schain_records: {records}')
    for r in records:
        logger.warning(f'Sending SIGTERM to {r.name}, {r.monitor_id}')
        terminate_process(r.monitor_id)
    logger.warning('All sChain processes stopped, exiting...')
    sys.exit(0)


def run_process_manager(skale, skale_ima, node_config):
    # signal.signal(signal.SIGTERM, pm_signal_handler)
    logger.info('Process manager started')
    node_id = node_config.id
    node_info = node_config.all()
    notify_if_not_enough_balance(skale, node_info)

    schains_to_monitor = fetch_schains_to_monitor(skale, node_id)
    for schain in schains_to_monitor:
        run_pm_schain(skale, skale_ima, node_config, schain)
    logger.info('Process manager procedure finished')


def run_pm_schain(skale, skale_ima, node_config, schain: Dict) -> None:
    schain_record = upsert_schain_record(schain['name'])
    process_report = ProcessReport(schain['name'])
    log_prefix = f'sChain {schain["name"]} -'  # todo - move to logger formatter

    dkg_timeout = skale.constants_holder.get_dkg_timeout()
    allowed_diff = int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)
    if int(time.time()) - process_report.ts > allowed_diff:
        terminate_process(process_report.pid)
    monitor_process_alive = is_monitor_process_alive(schain_record.monitor_id)

    if not monitor_process_alive:
        logger.info(f'{log_prefix} PID {schain_record.monitor_id} is not running, spawning...')
        process = Process(
            name=schain['name'],
            target=create_and_execute_pipelines,
            args=(
                skale,
                schain,
                node_config,
                skale_ima,
                schain_record
            )
        )
        process.start()
        schain_record.set_monitor_id(process.ident)
        logger.info(f'{log_prefix} Process started: PID = {process.ident}')
    else:
        logger.info(f'{log_prefix} Process is running: PID = {schain_record.monitor_id}')


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
        arguments_list_string({'Node ID': node_id, 'sChains on node': active_schains,
                               'Number of sChains on node': len(active_schains),
                               'Empty sChain structs': schains_holes}, 'Monitoring sChains'))
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
