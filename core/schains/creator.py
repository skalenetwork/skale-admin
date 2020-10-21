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
import shutil
import time
from concurrent.futures import as_completed, ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from multiprocessing import Process

from skale.skale_manager import spawn_skale_manager_lib


from core.schains.runner import (run_schain_container, run_ima_container,
                                 restart_container, set_rotation_for_schain,
                                 is_exited_with_zero)
from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.schains.helper import (init_schain_dir,
                                 get_schain_config_filepath,
                                 get_schain_proxy_file_path,
                                 get_schain_rotation_filepath)
from core.schains.config.generator import generate_schain_config_with_skale
from core.schains.config.helper import (get_allowed_endpoints,
                                        save_schain_config,
                                        update_schain_config)
from core.schains.volume import init_data_volume
from core.schains.checks import get_rotation_state, SChainChecks
from core.schains.dkg import run_dkg

from core.schains.runner import get_container_name
from core.schains.utils import notify_if_not_enough_balance

from tools.bls.dkg_client import DkgError
from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.containers import SCHAIN_CONTAINER
from tools.configs.ima import IMA_DATA_FILEPATH
from tools.iptables import (add_rules as add_iptables_rules,
                            remove_rules as remove_iptables_rules)
from tools.notifications.messages import notify_checks, notify_repair_mode
from tools.str_formatters import arguments_list_string
from web.models.schain import upsert_schain_record


logger = logging.getLogger(__name__)

CONTAINERS_DELAY = 20
JOIN_TIMEOUT = 3800


class MonitorMode(Enum):
    REGULAR = 0
    SYNC = 1
    RESTART = 2
    EXIT = 3


def run_creator(skale, node_config):
    process = Process(target=monitor, args=(skale, node_config))
    process.start()
    process.join(JOIN_TIMEOUT)
    process.terminate()
    process.join()


def monitor(skale, node_config):
    logger.info('Creator procedure started')
    skale = spawn_skale_manager_lib(skale)
    logger.info('Spawned new skale lib')
    node_id = node_config.id
    ecdsa_sgx_key_name = node_config.sgx_key_name
    logger.info('Fetching schains ...')
    schains = skale.schains.get_schains_for_node(node_id)
    logger.info('Get leaving_history for node ...')
    leaving_history = skale.node_rotation.get_leaving_history(node_id)
    for leaving_schain in leaving_history:
        schain = skale.schains.get(leaving_schain['id'])
        if skale.node_rotation.is_rotation_in_progress(schain['name']) and schain['name']:
            schain['active'] = True
            schains.append(schain)
    schains_on_node = sum(map(lambda schain: schain['active'], schains))
    schains_holes = len(schains) - schains_on_node
    logger.info(
        arguments_list_string({'Node ID': node_id, 'sChains on node': schains_on_node,
                               'Empty sChain structs': schains_holes}, 'Monitoring sChains'))
    node_info = node_config.all()
    notify_if_not_enough_balance(skale, node_info)

    logger.info('Starting schains ThreadPoolExecutor')

    with ThreadPoolExecutor(max_workers=max(1, schains_on_node)) as executor:
        futures = [
            executor.submit(
                monitor_schain,
                skale,
                node_info,
                schain,
                ecdsa_sgx_key_name
            )
            for schain in schains if schain['active']
        ]
        for future in as_completed(futures):
            future.result()
    logger.info('Creator procedure finished')


def is_backup_run(schain_record):
    return schain_record.first_run and not schain_record.new_schain and BACKUP_RUN


def get_monitor_mode(schain_record, rotation_state):
    if is_backup_run(schain_record) or schain_record.repair_mode:
        return MonitorMode.SYNC
    elif rotation_state['in_progress']:
        if rotation_state['exiting_node']:
            return MonitorMode.EXIT
        elif rotation_state['new_schain']:
            return MonitorMode.SYNC
        else:
            return MonitorMode.RESTART
    return MonitorMode.REGULAR


def monitor_schain(skale, node_info, schain, ecdsa_sgx_key_name):
    logger.info(f"Monitor for sChain {schain['name']}")
    skale = spawn_skale_manager_lib(skale)
    name = schain['name']
    node_id, sgx_key_name = node_info['node_id'], node_info['sgx_key_name']
    rotation = get_rotation_state(skale, name, node_id)
    logger.info(f'Rotation for {name}: {rotation}')

    rotation_id = rotation['rotation_id']
    finish_ts = rotation['finish_ts']
    finish_time = datetime.fromtimestamp(finish_ts)

    schain_record = upsert_schain_record(name)
    mode = get_monitor_mode(schain_record, rotation)

    checks = SChainChecks(name, node_id, rotation_id=rotation_id, log=True)
    checks_dict = checks.get_all()

    if schain_record.repair_mode or not checks_dict['exit_code_ok']:
        logger.info(f'REPAIR MODE was toggled for schain {schain["name"]}')
        notify_repair_mode(node_info, name)
        cleanup_schain_docker_entity(name)
        schain_record.set_repair_mode(False)

    if not checks_dict['exit_code_ok']:
        mode = MonitorMode.SYNC

    if not schain_record.first_run:
        notify_checks(name, node_info, checks_dict)

    schain_record.set_first_run(False)
    schain_record.set_new_schain(False)
    logger.info(f'Running monitor for sChain {name} in {mode.name} mode')

    if mode == MonitorMode.EXIT:
        logger.info(f'Finish time: {finish_time}')
        # ensure containers are working after update
        if not checks_dict['container']:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
        set_rotation_for_schain(schain_name=name, timestamp=finish_ts)

    elif mode == MonitorMode.SYNC:
        monitor_checks(
            skale=skale,
            schain=schain,
            checks=checks_dict,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation=rotation,
            schain_record=schain_record,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            sync=True
        )

    elif mode == MonitorMode.RESTART:
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
            set_rotation_for_schain(schain_name=name, timestamp=finish_ts)

    else:
        monitor_checks(
            skale=skale,
            schain=schain,
            checks=checks_dict,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation=rotation,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            schain_record=schain_record
        )


def repair_schain(skale, schain, start_ts, rotation_id, dutils=None):
    remove_schain_container(schain['name'])
    remove_schain_volume(schain['name'])
    logger.info(f'Running fresh container for {schain["name"]}')
    monitor_sync_schain_container(skale, schain, start_ts, rotation_id, dutils)


def cleanup_schain_docker_entity(schain_name: str) -> None:
    remove_schain_container(schain_name)
    remove_schain_volume(schain_name)


def copy_schain_ima_abi(name):
    abi_file_dest = get_schain_proxy_file_path(name)
    shutil.copyfile(IMA_DATA_FILEPATH, abi_file_dest)


def add_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def remove_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)


def check_container(schain_name, volume_required=False, dutils=None):
    dutils = dutils or DockerUtils()
    name = get_container_name(SCHAIN_CONTAINER, schain_name)
    info = dutils.get_info(name)
    if not dutils.container_found(info):
        logger.warning(f'sChain: {schain_name}. '
                       f'sChain container: {name} not found, trying to create.')
        if volume_required and not dutils.is_data_volume_exists(schain_name):
            logger.error(
                f'sChain: {schain_name}. Cannot create sChain container without data volume'
            )
        return True


def monitor_schain_container(schain, dutils=None):
    if check_container(schain['name'], volume_required=True):
        run_schain_container(schain, dutils=dutils)


def monitor_ima_container(schain_name: str):
    run_ima_container(schain_name)


def monitor_sync_schain_container(skale, schain, start_ts, rotation_id=0,
                                  dutils=None):
    def get_schain_public_key(schain_name, method):
        group_idx = skale.schains.name_to_id(schain_name)
        raw_public_key = method(group_idx)
        public_key_array = [*raw_public_key[0], *raw_public_key[1]]
        return ':'.join(map(str, public_key_array))

    if check_container(schain['name'], volume_required=True):
        if not rotation_id:
            public_key = get_schain_public_key(
                schain['name'],
                skale.key_storage.get_common_public_key
            )
        else:
            public_key = get_schain_public_key(
                schain['name'],
                skale.key_storage.get_previous_public_key
            )
        run_schain_container(schain, public_key=public_key, start_ts=start_ts,
                             dutils=dutils)


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
                   rotation, schain_record, ecdsa_sgx_key_name, sync=False):
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
        init_schain_config(skale, node_id, name, ecdsa_sgx_key_name)
    if not checks['volume']:
        init_data_volume(schain)
    if not checks['firewall_rules']:
        add_firewall_rules(name)
    if not checks['container']:
        if sync:
            finish_ts = rotation['finish_ts']
            monitor_sync_schain_container(skale, schain,
                                          finish_ts, rotation['rotation_id'])
        elif check_schain_rotated(name):
            logger.info(
                f'sChain {name} is stopped after rotation. Going to restart')
            remove_firewall_rules(name)
            config = generate_schain_config_with_skale(
                skale=skale,
                schain_name=name,
                node_id=node_id,
                rotation_id=rotation['rotation_id'],
                ecdsa_key_name=ecdsa_sgx_key_name
            ).to_dict()
            update_schain_config(config, name)
            add_firewall_rules(name)
            restart_container(SCHAIN_CONTAINER, schain)
        else:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
    if not checks['ima_container']:
        monitor_ima_container(name)


def check_schain_rotated(schain_name):
    schain_rotation_filepath = get_schain_rotation_filepath(schain_name)
    rotation_file_exists = os.path.exists(schain_rotation_filepath)
    zero_exit_code = is_exited_with_zero(schain_name)
    return rotation_file_exists and zero_exit_code


# TODO: Check for rotation earlier
def init_schain_config(skale, node_id, schain_name, ecdsa_sgx_key_name):
    config_filepath = get_schain_config_filepath(schain_name)
    if not os.path.isfile(config_filepath):
        logger.warning(
            f'sChain {schain_name}: sChain config not found: '
            f'{config_filepath}, trying to create.'
        )
        rotation_id = skale.schains.get_last_rotation_id(schain_name)
        schain_config = generate_schain_config_with_skale(
            skale=skale,
            schain_name=schain_name,
            node_id=node_id,
            rotation_id=rotation_id,
            ecdsa_key_name=ecdsa_sgx_key_name
        )
        save_schain_config(schain_config.to_dict(), schain_name)
