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
from typing import Optional

from sgx import SgxClient
from skale import Skale

from core.node import get_current_nodes, get_skale_node_version
from core.schains.checks import SChainChecks
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.directory import schain_config_dir
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.firewall.utils import get_default_rule_controller
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.schains.process import ProcessReport, terminate_process
from core.schains.runner import get_container_name, is_exited
from core.schains.external_config import ExternalConfig
from core.schains.types import ContainerType
from core.schains.firewall.utils import get_sync_agent_ranges

from tools.configs import SGX_CERTIFICATES_FOLDER, SYNC_NODE
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER, SCHAIN_STOP_TIMEOUT
from tools.docker_utils import DockerUtils
from tools.helper import merged_unique, read_json, is_node_part_of_chain
from tools.sgx_utils import SGX_SERVER_URL
from tools.str_formatters import arguments_list_string
from web.models.schain import get_schains_names, mark_schain_deleted, upsert_schain_record


logger = logging.getLogger(__name__)

JOIN_TIMEOUT = 1800


def run_cleaner(skale, node_config):
    process = Process(name='cleaner', target=monitor, args=(skale, node_config))
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
    return dutils.safe_rm(schain_container_name, v=True, force=True, timeout=SCHAIN_STOP_TIMEOUT)


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
    schain_names_on_contracts = get_schain_names_from_contract(skale, node_config.id)
    logger.info(f'\nsChains on contracts: {schain_names_on_contracts}\n\
sChains on node: {schains_on_node}')

    for schain_name in schains_on_node:
        if schain_name not in schain_names_on_contracts:
            logger.warning(f'sChain {schain_name} was found on node, but not on contracts: \
{schain_names_on_contracts}, going to remove it!')
            try:
                ensure_schain_removed(skale, schain_name, node_config.id, dutils=dutils)
            except Exception:
                logger.exception(f'sChain removal {schain_name} failed')
    logger.info('Cleanup procedure finished')


def get_schain_names_from_contract(skale, node_id):
    schains_on_contract = skale.schains.get_schains_for_node(node_id)
    return list(map(lambda schain: schain.name, schains_on_contract))


def get_schains_with_containers(dutils=None):
    dutils = dutils or DockerUtils()
    return [
        c.name.replace('skale_schain_', '', 1) for c in dutils.get_all_schain_containers(all=True)
    ]


def get_schains_on_node(dutils=None):
    dutils = dutils or DockerUtils()
    schains_with_dirs = os.listdir(SCHAINS_DIR_PATH)
    schains_with_container = get_schains_with_containers(dutils)
    schains_active_records = get_schains_names()
    return sorted(merged_unique(schains_with_dirs, schains_with_container, schains_active_records))


def schain_names_to_ids(skale, schain_names):
    ids = []
    for name in schain_names:
        id_ = skale.schains.name_to_id(name)
        ids.append(bytes.fromhex(id_))
    return ids


def ensure_schain_removed(skale, schain_name, node_id, dutils=None):
    dutils = dutils or DockerUtils()
    is_schain_exist = skale.schains_internal.is_schain_exist(schain_name)

    if not is_schain_exist:
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Going to remove this sChain because it was removed from contracts',
        )
        return remove_schain(skale, node_id, schain_name, msg, dutils=dutils)

    if skale.node_rotation.is_rotation_active(schain_name):
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Rotation is in progress (new group created), skipping cleaner',
        )
        logger.info(msg)
        return

    if not is_node_part_of_chain(skale, schain_name, node_id):
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Going to remove this sChain because this node is not in the group',
        )
        return remove_schain(skale, node_id, schain_name, msg, dutils=dutils)

    msg = arguments_list_string(
        {'sChain name': schain_name}, 'sChain do not satisfy removal condidions'
    )
    logger.warning(msg)


def remove_schain(
    skale: Skale,
    node_id: int,
    schain_name: str,
    msg: str,
    dutils: Optional[DockerUtils] = None,
) -> None:
    logger.warning(msg)
    report = ProcessReport(name=schain_name)
    if report.is_exist():
        terminate_process(report.pid)

    delete_bls_keys(skale, schain_name)
    sync_agent_ranges = get_sync_agent_ranges(skale)
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    rotation_id = rotation_data['rotation_id']
    estate = ExternalConfig(name=schain_name).get()
    current_nodes = get_current_nodes(skale, schain_name)
    group_index = skale.schains.name_to_group_id(schain_name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(group_index)

    cleanup_schain(
        node_id,
        schain_name,
        sync_agent_ranges,
        rotation_id=rotation_id,
        last_dkg_successful=last_dkg_successful,
        current_nodes=current_nodes,
        estate=estate,
        dutils=dutils,
    )


def cleanup_schain(
    node_id: int,
    schain_name: str,
    sync_agent_ranges: list,
    rotation_id: int,
    last_dkg_successful: bool,
    current_nodes: list,
    estate: ExternalConfig,
    dutils=None,
) -> None:
    dutils = dutils or DockerUtils()
    schain_record = upsert_schain_record(schain_name)

    rc = get_default_rule_controller(name=schain_name, sync_agent_ranges=sync_agent_ranges)
    stream_version = get_skale_node_version()
    checks = SChainChecks(
        schain_name,
        node_id,
        rule_controller=rc,
        stream_version=stream_version,
        schain_record=schain_record,
        current_nodes=current_nodes,
        rotation_id=rotation_id,
        estate=estate,
        last_dkg_successful=last_dkg_successful,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )
    check_status = checks.get_all()
    if check_status['skaled_container'] or is_exited(
        schain_name,
        container_type=ContainerType.schain,
        dutils=dutils
    ):
        remove_schain_container(schain_name, dutils=dutils)
    if check_status['volume']:
        remove_schain_volume(schain_name, dutils=dutils)
    if check_status['firewall_rules']:
        conf = ConfigFileManager(schain_name).skaled_config
        base_port = get_base_port_from_config(conf)
        own_ip = get_own_ip_from_config(conf)
        node_ips = get_node_ips_from_config(conf)
        ranges = []
        if estate is not None:
            ranges = estate.ranges
        rc.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips, sync_ip_ranges=ranges)
        rc.cleanup()
    if estate is not None and estate.ima_linked:
        if check_status.get('ima_container', False) or is_exited(
            schain_name,
            container_type=ContainerType.ima,
            dutils=dutils
        ):
            remove_ima_container(schain_name, dutils=dutils)
    if check_status['config_dir']:
        remove_config_dir(schain_name)
    mark_schain_deleted(schain_name)


def delete_bls_keys(skale, schain_name):
    last_rotation_id = skale.schains.get_last_rotation_id(schain_name)
    for i in range(last_rotation_id + 1):
        try:
            secret_key_share_filepath = get_secret_key_share_filepath(schain_name, i)
            if os.path.isfile(secret_key_share_filepath):
                secret_key_share_config = read_json(secret_key_share_filepath) or {}
                bls_key_name = secret_key_share_config.get('key_share_name')
                if bls_key_name:
                    sgx = SgxClient(SGX_SERVER_URL, path_to_cert=SGX_CERTIFICATES_FOLDER)
                    sgx.delete_bls_key(bls_key_name)
        except Exception:
            logger.exception(f'Removing secret_key for rotation {i} failed')
