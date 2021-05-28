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
from datetime import datetime
from multiprocessing import Process

import psutil
from skale import Skale

from core.schains.monitor import run_monitor_for_schain
from core.schains.utils import notify_if_not_enough_balance

from web.models.schain import upsert_schain_record
from tools.str_formatters import arguments_list_string
from tools.helper import check_pid


logger = logging.getLogger(__name__)


TIMEOUT_COEFFICIENT = 1.5


def run_process_manager(skale, skale_ima, node_config):
    logger.info('Process manager started')
    node_id = node_config.id
    ecdsa_sgx_key_name = node_config.sgx_key_name
    node_info = node_config.all()
    notify_if_not_enough_balance(skale, node_info)

    schains_to_monitor = fetch_schains_to_monitor(skale, node_id)

    for schain in schains_to_monitor:
        schain_record = upsert_schain_record(schain['name'])
        log_prefix = f'sChain {schain["name"]} -'  # todo - move to logger formatter

        terminate_stuck_schain_process(skale, schain_record, schain)
        monitor_process_alive = is_monitor_process_alive(schain_record.monitor_id)

        if not monitor_process_alive:
            logger.info(f'{log_prefix} Process wasn\'t found, doing to spawn')
            process = Process(target=run_monitor_for_schain, args=(
                skale,
                skale_ima,
                node_info,
                schain,
                ecdsa_sgx_key_name
            ))
            process.start()
            schain_record.set_monitor_id(process.ident)
            logger.info(f'{log_prefix} Process started: PID = {process.ident}')
        else:
            logger.info(f'{log_prefix} Process is running: PID = {schain_record.monitor_id}')
    logger.info('Creator procedure finished')


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
        schain = skale.schains.get(leaving_schain['id'])
        if skale.node_rotation.is_rotation_in_progress(schain['name']) and schain['name']:
            schain['active'] = True
            leaving_schains.append(schain)
    logger.info(f'Got leaving sChains for the node: {leaving_schains}')
    return leaving_schains


def terminate_stuck_schain_process(skale, schain_record, schain):
    """
    This function terminates the process if last_seen time is less than
    DKG timeout * TIMEOUT_COEFFICIENT
    """
    allowed_last_seen_time = calc_allowed_last_seen_time(skale)
    schain_monitor_last_seen = schain_record.monitor_last_seen.timestamp()
    if allowed_last_seen_time > schain_monitor_last_seen:
        logger.warning(f'schain: {schain["name"]}, pid {schain_record.monitor_id} last seen is \
{schain_monitor_last_seen}, while max allowed last_seen is {allowed_last_seen_time}, pid \
{schain_record.monitor_id} will be terminated now!')
        terminate_schain_process(schain_record)


def terminate_schain_process(schain_record):
    log_prefix = f'schain: {schain_record.name}, pid {schain_record.monitor_id}'
    try:
        logger.info(f'{log_prefix} - going to terminate')
        p = psutil.Process(schain_record.monitor_id)
        p.terminate()
        logger.info(f'{log_prefix} was terminated')
    except psutil.NoSuchProcess:
        logger.info(f'{log_prefix} - no such process')
    except Exception:
        logging.exception(f'{log_prefix} - termination failed!')


def is_monitor_process_alive(monitor_id):
    return monitor_id != 0 and check_pid(monitor_id)


def calc_allowed_last_seen_time(skale):
    allowed_diff = skale.constants_holder.get_dkg_timeout() * TIMEOUT_COEFFICIENT
    return datetime.now().timestamp() - allowed_diff
