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

import os
import shutil
import logging
import time
from datetime import datetime

from skale.manager_client import spawn_skale_lib


from tools.bls.dkg_client import DkgError
from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

from core.schains.runner import (run_schain_container, run_ima_container,
                                 run_schain_container_in_sync_mode,
                                 restart_container, set_rotation_for_schain,
                                 check_container_exit)
from core.schains.cleaner import remove_config_dir
from core.tg_bot import TgBot
from core.schains.helper import (init_schain_dir, get_schain_config_filepath,
                                 get_schain_proxy_file_path)
from core.schains.config import (generate_schain_config, save_schain_config,
                                 get_schain_env, get_allowed_endpoints, update_schain_config)
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks, check_for_rotation
from core.schains.ima import get_ima_env
from core.schains.dkg import run_dkg

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.configs.tg import TG_API_KEY, TG_CHAT_ID
from tools.configs.schains import IMA_DATA_FILEPATH
from tools.iptables import (add_rules as add_iptables_rules,
                            remove_rules as remove_iptables_rules)

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
dutils = DockerUtils()

CONTAINERS_DELAY = 20


def run_creator(skale, node_config):
    monitor(skale, node_config)


def monitor(skale, node_config):
    logger.info('Creator procedure started')
    skale = spawn_skale_lib(skale)
    logger.info('Spawned new skale lib')
    node_id = node_config.id
    logger.info('Fetching schains ...')
    schains = skale.schains_data.get_schains_for_node(node_id)
    logger.info('Get leaving_history for node ...')
    leaving_history = skale.schains_data.get_leaving_history(node_id)
    for history in leaving_history:
        schain = skale.schains_data.get(history[0])
        if time.time() < history[1] and schain['name']:
            schain['active'] = True
            schains.append(schain)
    schains_on_node = sum(map(lambda schain: schain['active'], schains))
    schains_holes = len(schains) - schains_on_node
    logger.info(
        arguments_list_string({'Node ID': node_id, 'sChains on node': schains_on_node,
                               'Empty sChain structs': schains_holes}, 'Monitoring sChains'))

    with ThreadPoolExecutor(max_workers=max(1, schains_on_node)) as executor:
        futures = [
            executor.submit(
                monitor_schain,
                skale,
                node_config.id,
                node_config.sgx_key_name,
                schain
            )
            for schain in schains if schain['active']
        ]
        for future in futures:
            future.result()
    logger.info('Creator procedure finished')


def monitor_schain(skale, node_id, sgx_key_name, schain):
    skale = spawn_skale_lib(skale)
    name = schain['name']
    rotation = check_for_rotation(skale, name, node_id)
    logger.info(f'Rotation for {name}: {rotation}')

    rotation_in_progress = rotation['result']
    new_schain = rotation['new_schain']
    exiting_node = rotation['exiting_node']
    rotation_id = rotation['rotation_id']
    finish_time_ts = rotation['finish_ts']
    finish_time = datetime.fromtimestamp(finish_time_ts)

    checks = SChainChecks(name, node_id, rotation_id=rotation_id, log=True)
    checks_dict = checks.get_all()
    bot = TgBot(TG_API_KEY, TG_CHAT_ID) if TG_API_KEY and TG_CHAT_ID else None

    if not SChainRecord.added(name):
        schain_record, _ = SChainRecord.add(name)
    else:
        schain_record = SChainRecord.get_by_name(name)

    if not schain_record.first_run:
        if bot and not checks.is_healthy():
            bot.send_schain_checks(checks)

    schain_record.set_first_run(False)
    if exiting_node and rotation_in_progress:
        logger.info(f'Node is exiting. sChain will be stoped at {finish_time}')

        # ensure containers are working after update
        if not checks_dict['container']:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
        set_rotation_for_schain(schain, finish_time_ts)

        return

    if rotation_in_progress and new_schain:
        logger.info('Building new rotated schain')
        monitor_checks(
            skale=skale,
            schain=schain,
            checks=checks_dict,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation=rotation,
            schain_record=schain_record,
            sync=True
        )
        return

    elif rotation_in_progress and not new_schain:
        logger.info('Schain was rotated. Rotation in progress')

        # ensure containers are working after update
        if not checks_dict['container']:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)

        is_dkg_done = safe_run_dkg(
            skale=skale,
            schain_name=name,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation_id=rotation_id,
            schain_record=schain_record
        )
        # TODO: do once
        if is_dkg_done:
            set_rotation_for_schain(schain, finish_time_ts)

        return
    else:
        logger.info('No rotation for schain')

    monitor_checks(
        skale=skale,
        schain=schain,
        checks=checks_dict,
        node_id=node_id,
        sgx_key_name=sgx_key_name,
        rotation=rotation,
        schain_record=schain_record
    )


# TODO: Check for rotation earlier
def init_schain_config(skale, node_id, schain_name):
    config_filepath = get_schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        logger.warning(
            f'sChain {schain_name}: sChain config not found: '
            f'{config_filepath}, trying to create.'
        )
        rotation_id = skale.schains_data.get_last_rotation_id(schain_name)
        schain_config = generate_schain_config(skale, schain_name, node_id, rotation_id)
        save_schain_config(schain_config, schain_name)


def copy_schain_ima_abi(name):
    abi_file_dest = get_schain_proxy_file_path(name)
    shutil.copyfile(IMA_DATA_FILEPATH, abi_file_dest)


def add_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def remove_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)


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


def safe_run_dkg(skale, schain_name, node_id, sgx_key_name,
                 rotation_id, schain_record):
    schain_record.dkg_started()
    try:
        run_dkg(skale, schain_name, node_id,
                sgx_key_name, rotation_id)
    except DkgError as err:
        logger.info(f'sChain {schain_name} Dkg procedure failed with {err}')
        schain_record.dkg_failed()
        return False
    schain_record.dkg_done()
    return True


def monitor_checks(skale, schain, checks, node_id, sgx_key_name,
                   rotation, schain_record, sync=False):
    name = schain['name']
    if not checks['data_dir']:
        init_schain_dir(name)
    if not checks['dkg']:
        is_dkg_done = safe_run_dkg(
            skale=skale,
            schain_name=name,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation_id=rotation['rotation_id'],
            schain_record=schain_record
        )
        if not is_dkg_done:
            remove_config_dir(name)
            return

    if not checks['config']:
        init_schain_config(skale, node_id, name)
    if not checks['volume']:
        init_data_volume(schain)
    if not checks['firewall_rules']:
        add_firewall_rules(name)
    if not checks['container']:
        if sync:
            finish_time_ts = rotation['finish_ts']
            monitor_sync_schain_container(skale, schain, finish_time_ts)
        elif check_container_exit(name, dutils=dutils):
            remove_firewall_rules(name)
            config = generate_schain_config(skale, name, node_id, rotation['rotation_id'])
            update_schain_config(config, name)
            add_firewall_rules(name)
            restart_container(SCHAIN_CONTAINER, schain)
        else:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
