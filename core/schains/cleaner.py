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
from multiprocessing import Process

from sgx import SgxClient

from core.schains.checks import SChainChecks
from core.schains.config.dir import schain_config_dir
from core.schains.runner import get_container_name, is_exited, is_exited_with_zero
from core.schains.config.helper import get_allowed_endpoints
from core.schains.types import ContainerType
from core.schains.process_manager_helper import terminate_schain_process

from core.schains.dkg.utils import get_secret_key_share_filepath
from tools.configs import SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import (
    SCHAIN_CONTAINER, IMA_CONTAINER, SCHAIN_STOP_TIMEOUT
)
from tools.configs.ima import DISABLE_IMA
from tools.docker_utils import DockerUtils
from tools.iptables import remove_rules as remove_iptables_rules
from tools.helper import merged_unique, read_json
from tools.sgx_utils import SGX_SERVER_URL
from tools.str_formatters import arguments_list_string
from web.models.schain import get_schains_names, mark_schain_deleted, upsert_schain_record


logger = logging.getLogger(__name__)

JOIN_TIMEOUT = 1800


def run_cleaner(skale, node_config):
    process = Process(target=monitor, args=(skale, node_config))
    process.start()
    logger.info('Cleaner process started')
    process.join(JOIN_TIMEOUT)
    logger.info('Cleaner process is joined.')
    logger.info('Terminating the process')
    process.terminate()
    process.join()


def log_remove(component_name, schain_name):
    logger.info(f'Going to remove {component_name} for sChain {schain_name}')


def remove_schain_volume(schain_name: str, dutils: DockerUtils = None) -> None:
    dutils = dutils or DockerUtils()
    log_remove('volume', schain_name)
    dutils.rm_vol(schain_name)


def remove_schain_container(schain_name: str, dutils: DockerUtils = None):
    dutils = dutils or DockerUtils()
    log_remove('container', schain_name)
    schain_container_name = get_container_name(SCHAIN_CONTAINER, schain_name)
    return dutils.safe_rm(
        schain_container_name,
        v=True,
        force=True,
        stop_timeout=SCHAIN_STOP_TIMEOUT
    )


def remove_ima_container(schain_name: str, dutils: DockerUtils = None):
    dutils = dutils or DockerUtils()
    log_remove('IMA container', schain_name)
    ima_container_name = get_container_name(IMA_CONTAINER, schain_name)
    dutils.safe_rm(ima_container_name, v=True, force=True)


def remove_config_dir(schain_name: str) -> None:
    log_remove('config directory', schain_name)
    schain_dir_path = schain_config_dir(schain_name)
    shutil.rmtree(schain_dir_path)


def monitor(skale, node_config, dutils=None):
    dutils = dutils or DockerUtils()
    logger.info('Cleaner procedure started.')
    schains_on_node = get_schains_on_node(dutils=dutils)
    schain_names_on_contracts = get_schain_names_from_contract(
        skale,
        node_config.id
    )
    logger.info(f'\nsChains on contracts: {schain_names_on_contracts}\n\
sChains on node: {schains_on_node}')

    for schain_name in schains_on_node:
        if schain_name not in schain_names_on_contracts:
            logger.warning(f'sChain {schain_name} was found on node, but not on contracts: \
{schain_names_on_contracts}, going to remove it!')
            try:
                ensure_schain_removed(
                    skale,
                    schain_name,
                    node_config.id,
                    dutils=dutils
                )
            except Exception:
                logger.exception(f'sChain removal {schain_name} failed')
    logger.info('Cleanup procedure finished')


def get_schain_names_from_contract(skale, node_id):
    schains_on_contract = skale.schains.get_schains_for_node(node_id)
    return list(map(lambda schain: schain['name'], schains_on_contract))


def get_schains_with_containers(dutils=None):
    dutils = dutils or DockerUtils()
    return [
        c.name.replace('skale_schain_', '', 1)
        for c in dutils.get_all_schain_containers(all=True)
    ]


def get_schains_on_node(dutils=None):
    dutils = dutils or DockerUtils()
    schains_with_dirs = os.listdir(SCHAINS_DIR_PATH)
    schains_with_container = get_schains_with_containers(dutils)
    schains_active_records = get_schains_names()
    return sorted(merged_unique(
        schains_with_dirs,
        schains_with_container,
        schains_active_records
    ))


def schain_names_to_ids(skale, schain_names):
    ids = []
    for name in schain_names:
        id_ = skale.schains.name_to_id(name)
        ids.append(bytes.fromhex(id_))
    return ids


def remove_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)


def ensure_schain_removed(skale, schain_name, node_id, dutils=None):
    dutils = dutils or DockerUtils()
    is_schain_exist = skale.schains_internal.is_schain_exist(schain_name)
    exited_with_zero = is_exited_with_zero(schain_name, dutils=dutils)
    schain_record = upsert_schain_record(schain_name)

    msg = arguments_list_string(
        {'sChain name': schain_name},
        'sChain do not satisfy removal condidions'
    )
    if exited_with_zero:
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Going to remove this sChain because it was rotated'
        )
    if not is_schain_exist:
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Going to remove this sChain because it was removed from contracts'
        )

    if exited_with_zero or not is_schain_exist:
        logger.warning(msg)
        terminate_schain_process(schain_record)
        delete_bls_keys(skale, schain_name)
        cleanup_schain(node_id, schain_name, dutils=dutils)
        return
    logger.info(msg)


def cleanup_schain(node_id, schain_name, dutils=None):
    dutils = dutils or DockerUtils()
    schain_record = upsert_schain_record(schain_name)
    checks = SChainChecks(schain_name, node_id, schain_record=schain_record)
    if checks.container or is_exited(
        schain_name,
        container_type=ContainerType.schain,
        dutils=dutils
    ):
        remove_schain_container(schain_name, dutils=dutils)
    if checks.volume:
        remove_schain_volume(schain_name, dutils=dutils)
    if checks.firewall_rules:
        remove_firewall_rules(schain_name)
    if not DISABLE_IMA:
        if checks.ima_container or is_exited(
            schain_name,
            container_type=ContainerType.ima,
            dutils=dutils
        ):
            remove_ima_container(schain_name, dutils=dutils)
    if checks.config_dir:
        remove_config_dir(schain_name)
    mark_schain_deleted(schain_name)


def delete_bls_keys(skale, schain_name):
    last_rotation_id = skale.schains.get_last_rotation_id(schain_name)
    for i in range(last_rotation_id + 1):
        try:
            secret_key_share_filepath = get_secret_key_share_filepath(
                schain_name, i)
            if os.path.isfile(secret_key_share_filepath):
                secret_key_share_config = read_json(
                    secret_key_share_filepath) or {}
                bls_key_name = secret_key_share_config.get('key_share_name')
                if bls_key_name:
                    sgx = SgxClient(SGX_SERVER_URL,
                                    path_to_cert=SGX_CERTIFICATES_FOLDER)
                    sgx.delete_bls_key(bls_key_name)
        except Exception:
            logger.exception(f'Removing secret_key for rotation {i} failed')
