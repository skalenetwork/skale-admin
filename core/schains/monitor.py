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
import signal
from enum import Enum
from importlib import reload
from datetime import datetime

from skale.schain_config.generator import get_nodes_for_schain
from web3._utils import request

from core.schains.dkg_status import DKGStatus
from core.schains.runner import (run_schain_container, run_ima_container,
                                 restart_container, set_rotation_for_schain,
                                 is_exited_with_zero)
from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.ima.schain import copy_schain_ima_abi
from core.schains.helper import init_schain_dir, get_schain_rotation_filepath
from core.schains.config.generator import init_schain_config
from core.schains.config.helper import get_allowed_endpoints
from core.schains.volume import init_data_volume
from core.schains.checks import SChainChecks
from core.schains.rotation import get_rotation_state
from core.schains.dkg import run_dkg, save_dkg_results

from core.schains.runner import get_container_name

from tools.bls.dkg_client import DkgError, KeyGenerationError
from tools.bls.dkg_utils import init_dkg_client, get_secret_key_share_filepath, generate_bls_keys
from tools.docker_utils import DockerUtils
from tools.configs import BACKUP_RUN
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from tools.configs.ima import DISABLE_IMA
from tools.iptables import (add_rules as add_iptables_rules,
                            remove_rules as remove_iptables_rules)
from tools.notifications.messages import notify_checks, notify_repair_mode, is_checks_passed
from web.models.schain import upsert_schain_record, SChainRecord


logger = logging.getLogger(__name__)

CONTAINERS_DELAY = 20
SCHAIN_MONITOR_SLEEP_INTERVAL = 500


class MonitorMode(Enum):
    REGULAR = 0
    SYNC = 1
    RESTART = 2
    EXIT = 3


def run_monitor_for_schain(
        skale, skale_ima, node_info, schain, ecdsa_sgx_key_name, loop=True):
    prefix = f'schain: {schain["name"]} -'
    try:
        logger.info(f'{prefix} monitor created')
        reload(request)  # fix for web3py multiprocessing issue (see SKALE-4251)
        while True:
            logger.info(f'schain: {schain["name"]} - running monitor')
            schain_record = upsert_schain_record(schain["name"])
            schain_record.set_monitor_last_seen(datetime.now())

            def signal_handler(*args):
                schain_index = skale.schains.name_to_group_id(schain["name"])
                num_of_nodes = len(get_nodes_for_schain(skale, schain["name"]))
                if skale.dkg.get_number_of_completed(schain_index) == num_of_nodes:
                    schain_record.dkg_key_generation_error()
                else:
                    schain_record.failed()
                os.kill(os.getpid(), signal.SIGTERM)

            signal.signal(signal.SIGTERM, signal_handler)

            monitor_schain(
                skale,
                skale_ima,
                node_info,
                schain,
                ecdsa_sgx_key_name
            )
            schain_record = upsert_schain_record(schain['name'])
            schain_record.set_monitor_last_seen(datetime.now())

            if not loop:
                logger.warning(f'{prefix} finishing monitor')
                return

            logger.info(f'{prefix} sleeping {SCHAIN_MONITOR_SLEEP_INTERVAL}s...')
            time.sleep(SCHAIN_MONITOR_SLEEP_INTERVAL)
    except Exception:
        logger.exception(f'{prefix} monitor failed')


def monitor_schain(skale, skale_ima, node_info, schain, ecdsa_sgx_key_name):
    name = schain['name']
    node_id, sgx_key_name = node_info['node_id'], node_info['sgx_key_name']
    rotation = get_rotation_state(skale, name, node_id)

    rotation_id = rotation['rotation_id']
    finish_ts = rotation['finish_ts']
    finish_time = datetime.fromtimestamp(finish_ts)

    schain_record = upsert_schain_record(name)
    mode = get_monitor_mode(schain_record, rotation)
    checks = SChainChecks(name, node_id, rotation_id=rotation_id)

    logger.debug(f'schain_record: {SChainRecord.to_dict(schain_record)}, rotation: {rotation}')

    if schain_record.needs_reload:
        logger.warning(f'Going to reload {schain["name"]}')
        remove_schain_container(schain["name"])
        schain_record.set_needs_reload(False)
        mode = MonitorMode.REGULAR
        logger.warning(f'sChain container {schain["name"]} was removed, going to run checks')

    if schain_record.repair_mode or not checks.exit_code_ok:
        logger.warning(f'REPAIR MODE was toggled for schain {schain["name"]}, \
repair_mode: {schain_record.repair_mode}, exit_code_ok: {checks.exit_code_ok}')
        mode = MonitorMode.SYNC
        notify_repair_mode(node_info, name)
        schain_record.set_repair_mode(False)

    if not schain_record.first_run:
        checks_dict = checks.get_all()
        if not is_checks_passed(checks_dict):
            notify_checks(name, node_info, checks_dict)

    schain_record.set_first_run(False)
    schain_record.set_new_schain(False)
    logger.info(f'Running monitor for sChain {name} in {mode.name} mode')

    if mode == MonitorMode.EXIT:
        logger.info(f'Finish time: {finish_time}')
        # ensure containers are working after update
        if not checks.container:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
        set_rotation_for_schain(schain_name=name, timestamp=finish_ts)

    elif mode == MonitorMode.SYNC:
        if not rotation['new_schain']:
            cleanup_schain_docker_entity(name)
        monitor_checks(
            skale=skale,
            skale_ima=skale_ima,
            schain=schain,
            checks=checks,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation=rotation,
            schain_record=schain_record,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            sync=True
        )

    elif mode == MonitorMode.RESTART:
        # ensure containers are working after update
        if not checks.container:
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
            skale_ima=skale_ima,
            schain=schain,
            checks=checks,
            node_id=node_id,
            sgx_key_name=sgx_key_name,
            rotation=rotation,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            schain_record=schain_record
        )


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


def cleanup_schain_docker_entity(schain_name: str) -> None:
    remove_schain_container(schain_name)
    time.sleep(10)
    remove_schain_volume(schain_name)


def add_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    add_iptables_rules(endpoints)


def remove_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)


def is_volume_exists(schain_name, dutils=None):
    dutils = dutils or DockerUtils()
    return dutils.is_data_volume_exists(schain_name)


def is_container_exists(schain_name,
                        container_type=SCHAIN_CONTAINER, dutils=None):
    dutils = dutils or DockerUtils()
    container_name = get_container_name(container_type, schain_name)
    return dutils.is_container_exists(container_name)


def monitor_schain_container(schain, volume_required=True, dutils=None):
    schain_name = schain['name']
    if volume_required and not is_volume_exists(schain_name):
        logger.error(f'Data volume for sChain {schain_name} does not exist')
        return

    if not is_container_exists(schain_name):
        run_schain_container(schain, dutils=dutils)


def monitor_ima_container(schain: dict, mainnet_chain_id: int, dutils=None):
    if not is_container_exists(schain['name'],
                               container_type=IMA_CONTAINER, dutils=dutils):
        run_ima_container(schain, mainnet_chain_id)


def get_schain_public_key(skale, schain_name):
    group_idx = skale.schains.name_to_id(schain_name)
    raw_public_key = skale.key_storage.get_previous_public_key(group_idx)
    public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    if public_key_array == ['0', '0', '1', '0']:  # zero public key
        raw_public_key = skale.key_storage.get_common_public_key(group_idx)
        public_key_array = [*raw_public_key[0], *raw_public_key[1]]
    return ':'.join(map(str, public_key_array))


def monitor_sync_schain_container(skale, schain, start_ts,
                                  volume_required=True,
                                  dutils=None):
    schain_name = schain['name']
    if volume_required and not is_volume_exists(schain_name):
        logger.error(f'Data volume for sChain {schain_name} does not exist')
        return

    if not is_container_exists(schain_name):
        public_key = get_schain_public_key(skale, schain_name)
        run_schain_container(schain, public_key=public_key, start_ts=start_ts,
                             dutils=dutils)


def safe_run_dkg(skale, schain_name, node_id, sgx_key_name,
                 rotation_id, schain_record):
    if schain_record.dkg_status == DKGStatus.KEY_GENERATION_ERROR:
        try:
            dkg_client = init_dkg_client(node_id, schain_name, skale, sgx_key_name)
        except DkgError as err:
            logger.info(f'sChain {schain_name} Dkg procedure failed with {err}')
            schain_record.dkg_failed()
            return False

        try:
            dkg_results = generate_bls_keys(dkg_client, rotation_id)
            secret_key_share_filepath = get_secret_key_share_filepath(schain_name, rotation_id)
            save_dkg_results(dkg_results, secret_key_share_filepath)
        except KeyGenerationError as err:
            logger.info(f'sChain {schain_name} Dkg procedure failed on key generation with {err}')
            schain_record.dkg_key_generation_error()
            return False
        except DkgError as err:
            logger.info(f'sChain {schain_name} Dkg procedure failed with {err}')
            schain_record.dkg_failed()
            return False
        schain_record.dkg_done()
        return True

    schain_record.dkg_started()
    try:
        if not skale.dkg.is_channel_opened(skale.schains.name_to_group_id(schain_name)):
            schain_record.dkg_failed()
            return False
        run_dkg(skale, schain_name, node_id,
                sgx_key_name, rotation_id)
    except KeyGenerationError as err:
        logger.info(f'sChain {schain_name} Dkg procedure failed on key generation with {err}')
        schain_record.dkg_key_generation_error()
        return False
    except DkgError as err:
        logger.info(f'sChain {schain_name} Dkg procedure failed with {err}')
        schain_record.dkg_failed()
        return False
    schain_record.dkg_done()
    return True


def monitor_checks(skale, skale_ima, schain, checks, node_id, sgx_key_name,
                   rotation, schain_record, ecdsa_sgx_key_name, sync=False):
    name = schain['name']
    mainnet_chain_id = skale.web3.eth.chainId
    logger.debug(f'Mainnet chainId: {mainnet_chain_id}')
    if not checks.data_dir:
        init_schain_dir(name)
    if not checks.dkg:
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

    if not checks.config:
        rotation_id = skale.schains.get_last_rotation_id(name)
        init_schain_config(
            skale=skale,
            node_id=node_id,
            schain_name=name,
            ecdsa_sgx_key_name=ecdsa_sgx_key_name,
            rotation_id=rotation_id
        )
    if not checks.volume:
        init_data_volume(schain)
    if not checks.firewall_rules:
        add_firewall_rules(name)
    if not checks.container:
        if sync:
            finish_ts = rotation['finish_ts']
            monitor_sync_schain_container(skale, schain, finish_ts)
        elif check_schain_rotated(name):
            logger.info(
                f'sChain {name} is stopped after rotation. Going to restart')
            remove_firewall_rules(name)
            init_schain_config(
                skale=skale,
                schain_name=name,
                node_id=node_id,
                ecdsa_sgx_key_name=ecdsa_sgx_key_name,
                rotation_id=rotation['rotation_id']
            )
            add_firewall_rules(name)
            restart_container(SCHAIN_CONTAINER, schain)
        else:
            monitor_schain_container(schain)
            time.sleep(CONTAINERS_DELAY)
    if not DISABLE_IMA and not checks.ima_container:
        monitor_ima(skale_ima, schain, mainnet_chain_id)


def monitor_ima(skale_ima, schain, mainnet_chain_id, dutils=None):
    if skale_ima.linker.has_schain(schain['name']):  # todo: add IMA version check
        copy_schain_ima_abi(schain['name'])
        monitor_ima_container(schain, mainnet_chain_id, dutils=dutils)
    else:
        logger.warning(f'sChain {schain["name"]} is not registered in IMA')


def check_schain_rotated(schain_name):
    schain_rotation_filepath = get_schain_rotation_filepath(schain_name)
    rotation_file_exists = os.path.exists(schain_rotation_filepath)
    zero_exit_code = is_exited_with_zero(schain_name)
    return rotation_file_exists and zero_exit_code
