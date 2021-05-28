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

from skale import Skale


from core.schains.utils import notify_if_not_enough_balance

from web.models.schain import upsert_schain_record, SChainRecord
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)


def run_process_manager(skale, skale_ima, node_config):
    logger.info('Process manager started')
    node_id = node_config.id
    ecdsa_sgx_key_name = node_config.sgx_key_name
    node_info = node_config.all()
    notify_if_not_enough_balance(skale, node_info)

    schains_to_monitor = fetch_schains_to_monitor(skale, node_id)

    for schain in schains_to_monitor:
        schain_record = upsert_schain_record(schain['name'])

        terminate_stuck_process(skale, schain_record, schain)
        monitor_process_alive = is_monitor_process_alive(schain_record.monitor_id)

        if not monitor_process_alive:
            logger.info(f'Process for sChain {schain["name"]} wasn\'t found, doing to spawn')
            process = Process(target=run_monitor_for_schain, args=(
                skale,
                skale_ima,
                node_info,
                schain,
                ecdsa_sgx_key_name
            ))
            process.start()
            schain_record.set_monitor_id(process.ident)
            logger.info(f'Process for sChain {schain["name"]} started: PID = {process.ident}')
        else:
            logger.info(f'Process for sChain {schain["name"]} already running: \
PID = {schain_record.monitor_id}')
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