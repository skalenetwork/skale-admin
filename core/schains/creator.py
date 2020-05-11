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
import os
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from skale.manager_client import spawn_skale_lib


from tools.bls.dkg_client import DkgError
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

from core.schains.runner import (run_schain_container, run_ima_container,
                                 run_schain_container_in_sync_mode,
                                 restart_container)
from core.schains.cleaner import cleanup_schain, remove_config_dir
from core.schains.helper import (init_schain_dir, get_schain_config_filepath)
from core.schains.config import (generate_schain_config, save_schain_config,
                                 get_schain_env, get_allowed_endpoints)
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_env
from core.schains.dkg import run_dkg

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from tools.iptables import add_rules as add_iptables_rules

from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process

logger = logging.getLogger(__name__)
dutils = DockerUtils()

CONTAINERS_DELAY = 20


def run_creator(skale, node_config):
    process = Process(target=monitor, args=(skale, node_config))
    process.start()
    process.join()


def monitor(skale, node_config):
    logger.info('Creator procedure started')
    skale = spawn_skale_lib(skale)
    node_id = node_config.id
    schains = skale.schains_data.get_schains_for_node(node_id)
    schains_on_node = sum(map(lambda schain: schain['active'], schains))
    schains_holes = len(schains) - schains_on_node
    logger.info(
        arguments_list_string({'Node ID': node_id, 'sChains on node': schains_on_node,
                               'Empty sChain structs': schains_holes}, 'Monitoring sChains'))

    scheduler = BackgroundScheduler()
    scheduler.start()
    with ThreadPoolExecutor(max_workers=max(1, schains_on_node)) as executor:
        futures = [
            executor.submit(
                monitor_schain,
                skale,
                node_config.id,
                node_config.sgx_key_name,
                schain,
                scheduler
            )
            for schain in schains if schain['active']
        ]
        for future in futures:
            future.result()
    logger.info('Creator procedure finished')


def monitor_schain(skale, node_id, sgx_key_name, schain, scheduler):
    skale = spawn_skale_lib(skale)
    name = schain['name']
    checks = SChainChecks(name, node_id, log=True).get_all()

    if not SChainRecord.added(name):
        schain_record, _ = SChainRecord.add(name)
    else:
        schain_record = SChainRecord.get_by_name(name)

    if not schain_record.first_run:
        # todo: send failed checks to tg
        pass
    schain_record.set_first_run(False)

    rotation_in_progress = checks['rotation_in_progress']['result']
    new_schain = checks['rotation_in_progress']['new_schain']
    exiting_node = checks['rotation_in_progress']['exiting_node']
    rotation_id = checks['rotation_in_progress']['rotation_id']
    finish_time_ts = checks['rotation_in_progress']['finish_ts']
    finish_time = datetime.fromtimestamp(finish_time_ts)

    if exiting_node and rotation_in_progress:
        logger.info(f'Node is exiting. sChain will be stoped at {finish_time}')
        jobs = sum(map(lambda job: job.name == name, scheduler.get_jobs()))
        if jobs == 0:
            scheduler.add_job(cleanup_schain, 'date', run_date=finish_time,
                              name=name, args=[skale, name, node_id])
        return

    if rotation_in_progress and new_schain:
        logger.info('Building new rotated schain')
        jobs = sum(map(lambda job: job.name == name, scheduler.get_jobs()))
        if jobs == 0:
            schain_record.dkg_started()
            try:
                run_dkg(skale, schain['name'], node_id,
                        sgx_key_name, rotation_id)
            except DkgError as err:
                logger.info(f'sChain {name} Dkg procedure failed with {err}')
                schain_record.dkg_failed()
                remove_config_dir(schain['name'])
                return
            schain_record.dkg_done()
            schain_config = generate_schain_config(skale, schain['name'],
                                                   node_id, rotation_id)
            save_schain_config(schain_config, schain['name'])
            init_data_volume(schain)
            add_firewall_rules(name)
            time.sleep(CONTAINERS_DELAY)
            monitor_sync_schain_container(schain, finish_time_ts)
            monitor_ima_container(schain)
            # TODO: remove
            scheduler.add_job(print, 'date', run_date=finish_time,
                              name=name)
        return

    elif rotation_in_progress and not new_schain:
        logger.info('Schain was rotated. Rotation in progress')
        jobs = sum(map(lambda job: job.name == name, scheduler.get_jobs()))
        if jobs == 0:
            schain_record.dkg_started()
            try:
                run_dkg(skale, schain['name'], node_id,
                        sgx_key_name, rotation_id)
            except DkgError as err:
                logger.info(f'sChain {name} Dkg procedure failed with {err}')
                schain_record.dkg_failed()
                remove_config_dir(schain['name'])
            else:
                schain_record.dkg_done()
                scheduler.add_job(rotate_schain,
                                  'date', run_date=finish_time,
                                  name=name, args=[schain, rotation_id])
        logger.info(f'sChain will be restarted at {finish_time}')
        return
    else:
        logger.info('No rotation for schain')

    if not checks['data_dir']:
        init_schain_dir(name)
    if not checks['dkg']:
        try:
            schain_record.dkg_started()
            run_dkg(skale, schain['name'], node_id, sgx_key_name)
        except DkgError as err:
            logger.info(f'sChain {name} Dkg procedure failed with {err}')
            schain_record.dkg_failed()
            remove_config_dir(schain['name'])
            return
        schain_record.dkg_done()

    if not checks['config']:
        init_schain_config(skale, node_id, name)
    if not checks['volume']:
        init_data_volume(schain)
    if not checks['firewall_rules']:
        add_firewall_rules(name)
    if not checks['container']:
        monitor_schain_container(schain)
    time.sleep(CONTAINERS_DELAY)
    if not checks['ima_container']:
        monitor_ima_container(schain)


def init_schain_config(skale, node_id, schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        logger.warning(
            f'sChain {schain_name}: sChain config not found: '
            f'{config_filepath}, trying to create.'
        )
        schain_config = generate_schain_config(skale, schain_name, node_id)
        save_schain_config(schain_config, schain_name)


def add_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def check_container(schain_name, volume_required=False):
    name = get_container_name(SCHAIN_CONTAINER, schain_name)
    info = dutils.get_info(name)
    if dutils.to_start_container(info):
        logger.warning(f'sChain: {schain_name}. '
                       f'sChain container: {name} not found, trying to create.')
        if volume_required and not dutils.data_volume_exists(schain_name):
            logger.error(
                f'sChain: {schain_name}. Cannot create sChain container without data volume'
            )
        return True


def monitor_schain_container(schain):
    if check_container(schain['name'], volume_required=True):
        env = get_schain_env(schain['name'])
        run_schain_container(schain, env)


def monitor_ima_container(schain):
    env = get_ima_env(schain['name'])
    run_ima_container(schain, env)


def monitor_sync_schain_container(skale, schain, start_ts):
    def get_previous_schain_public_key(schain_name):
        group_idx = skale.schains_data.name_to_id(schain_name)
        raw_public_key = skale.schains_data.get_previous_groups_public_key(group_idx)
        return ':'.join(map(str, raw_public_key))

    if check_container(schain['name'], volume_required=True):
        env = get_schain_env(schain['name'])
        public_key = get_previous_schain_public_key(schain['name'])
        run_schain_container_in_sync_mode(schain,
                                          env,
                                          start_ts=start_ts,
                                          public_key=public_key)


def rotate_schain(skale, node_id, schain, rotation_id):
    logger.info('Schain was rotated. Regenerating config')
    schain_config = generate_schain_config(skale, schain['name'],
                                           node_id, rotation_id)
    save_schain_config(schain_config, schain['name'])
    logger.info('Containers are going to be restarted')
    restart_container(SCHAIN_CONTAINER, schain)
    restart_container(IMA_CONTAINER, schain)
