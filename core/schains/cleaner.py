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

import glob
import logging
import os
import shutil
from multiprocessing import Process
from pathlib import Path
from typing import Optional

from sgx import SgxClient
from skale import SkaleManager
from skale.types.node import NodeId
from skale.types.schain import SchainName, SchainStructure
from skale.utils.helper import schain_name_to_hash
from skale_core.settings import FairSettings, SkaleSettings, get_settings

from core.chain.runner import get_container_name, is_exited
from core.checks.schain import SChainChecks
from core.config.schain.directory import schain_config_dir
from core.dkg.utils import get_secret_key_share_filepath
from core.firewall.utils import cleanup_firewall_for_schain, get_default_rule_controller
from core.manager_cache import ManagerCache
from core.node import get_current_nodes, get_skale_node_version
from core.node_config import NodeConfig
from core.schains.external_config import ExternalConfig
from core.schains.process import ProcessReport, terminate_process
from core.schains.types import ContainerType
from tools.constants import NFT_CHAIN_CONFIG_WILDCARD, SGX_CERTIFICATES_FOLDER
from tools.constants.containers import IMA_CONTAINER, SKALED_CONTAINER
from tools.constants.schains import SCHAINS_DIR_PATH
from tools.docker_utils import DockerUtils
from tools.helper import is_node_part_of_chain, is_passive, merged_unique, read_json
from tools.str_formatters import arguments_list_string
from web.models.schain import get_schains_names, mark_schain_deleted, upsert_schain_record

logger = logging.getLogger(__name__)

JOIN_TIMEOUT = 1800

FAIR_NFT_CHAIN_NAMES = ['fair-network', 'fair-committee']


def run_cleaner(skale: SkaleManager, node_config: NodeConfig, manager_cache: ManagerCache) -> None:
    process = Process(name='cleaner', target=monitor, args=(skale, node_config, manager_cache))
    process.start()
    logger.info('Cleaner process started')
    process.join(JOIN_TIMEOUT)
    logger.info('Cleaner process is joined.')
    logger.info('Terminating the process')
    process.terminate()
    process.join()


def log_remove(component_name, schain_name):
    logger.info(f'Going to remove {component_name} for sChain {schain_name}')


def remove_schain_volume(schain_name: str, dutils: DockerUtils | None = None) -> None:
    dutils = dutils or DockerUtils()
    log_remove('volume', schain_name)
    dutils.rm_vol(schain_name)


def remove_skaled_container(schain_name: str, dutils: DockerUtils | None = None):
    dutils = dutils or DockerUtils()
    st = get_settings()
    log_remove('container', schain_name)
    schain_container_name = get_container_name(SKALED_CONTAINER, schain_name)
    return dutils.safe_rm(
        schain_container_name, v=True, force=True, timeout=st.container_stop_timeout
    )


def remove_ima_container(schain_name: str, dutils: DockerUtils | None = None):
    dutils = dutils or DockerUtils()
    log_remove('IMA container', schain_name)
    ima_container_name = get_container_name(IMA_CONTAINER, schain_name)
    dutils.safe_rm(ima_container_name, v=True, force=True)


def remove_config_dir(schain_name: str) -> None:
    log_remove('config directory', schain_name)
    schain_dir_path = schain_config_dir(schain_name)
    shutil.rmtree(schain_dir_path)


def monitor(skale: SkaleManager, node_config: NodeConfig, manager_cache: ManagerCache, dutils=None):
    dutils = dutils or DockerUtils()
    logger.info('Cleaner procedure started.')
    schains_on_node = get_schains_on_node(dutils=dutils)
    schain_names_on_contracts = get_schain_names_from_contract(manager_cache.schains)
    logger.info(
        f'\nsChains on contracts: {schain_names_on_contracts}\n\
sChains on node: {schains_on_node}'
    )

    for schain_name in schains_on_node:
        if schain_name not in schain_names_on_contracts:
            logger.info(
                '%s was found on node, but not on contracts: %s, trying to cleanup',
                schain_name,
                schain_names_on_contracts,
            )
            if schain_name == '':
                logger.warning('Found phantom schain on node')
                continue
            try:
                ensure_schain_removed(
                    skale, schain_name, node_config.id, manager_cache=manager_cache, dutils=dutils
                )
            except Exception:
                logger.exception('%s removal failed', schain_name)
    logger.info('Cleanup procedure finished')


def get_schain_names_from_contract(schains: list[SchainStructure]) -> list:
    return list(map(lambda schain: schain.name, schains))


def get_schains_with_containers(dutils=None):
    dutils = dutils or DockerUtils()
    return [c.name.replace('sk_skaled_', '', 1) for c in dutils.get_all_schain_containers(all=True)]


def get_schains_firewall_configs() -> list:
    return list(
        filter(
            lambda name: name not in FAIR_NFT_CHAIN_NAMES,
            map(lambda path: Path(path).stem, glob.glob(NFT_CHAIN_CONFIG_WILDCARD)),
        )
    )


def get_schains_on_node(dutils=None):
    dutils = dutils or DockerUtils()
    schains_with_dirs = os.listdir(SCHAINS_DIR_PATH)
    schains_with_container = get_schains_with_containers(dutils)
    schains_active_records = get_schains_names()
    schains_firewall_configs = list(
        map(lambda name: name.removeprefix('skale-'), get_schains_firewall_configs())
    )
    logger.info(
        'dirs %s, containers: %s, records: %s, firewall configs: %s',
        schains_with_dirs,
        schains_with_container,
        schains_active_records,
        schains_firewall_configs,
    )
    return sorted(
        merged_unique(
            schains_with_dirs,
            schains_with_container,
            schains_active_records,
            schains_firewall_configs,
        )
    )


def ensure_schain_removed(
    skale: SkaleManager,
    schain_name: SchainName,
    node_id: NodeId,
    manager_cache: ManagerCache,
    dutils=None,
):
    dutils = dutils or DockerUtils()
    is_schain_exist = skale.schains_internal.is_schain_exist(schain_name)

    if not is_schain_exist:
        msg = arguments_list_string(
            {'sChain name': schain_name},
            'Going to remove this sChain because it was removed from contracts',
        )
        return remove_schain(
            skale, node_id, schain_name, msg, manager_cache=manager_cache, dutils=dutils
        )

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
        return remove_schain(
            skale, node_id, schain_name, msg, manager_cache=manager_cache, dutils=dutils
        )

    msg = arguments_list_string(
        {'sChain name': schain_name}, 'sChain do not satisfy removal condidions'
    )
    logger.warning(msg)


def remove_schain(
    skale: SkaleManager,
    node_id: int,
    schain_name: SchainName,
    msg: str,
    manager_cache: ManagerCache,
    dutils: Optional[DockerUtils] = None,
) -> None:
    logger.warning(msg)
    report = ProcessReport(name=schain_name)
    if report.exists():
        terminate_process(report.pid)

    delete_bls_keys(skale, schain_name)

    sync_agent_ranges = manager_cache.sync_ranges
    schain_hash = schain_name_to_hash(schain_name)
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    rotation_id = rotation_data.rotation_counter
    estate = ExternalConfig(name=schain_name).get()
    current_nodes = get_current_nodes(skale, schain_hash, manager_cache)
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
    schain_name: SchainName,
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
        passive_node=is_passive(),
    )
    check_status = checks.get_all()
    if check_status['skaled_container'] or is_exited(
        schain_name, container_type=ContainerType.skaled, dutils=dutils
    ):
        remove_skaled_container(schain_name, dutils=dutils)
    if check_status['volume']:
        remove_schain_volume(schain_name, dutils=dutils)
    if any(checks.firewall_rules.data):
        logger.info('Cleaning firewall for %s', schain_name)
        cleanup_firewall_for_schain(schain_name)

    if estate is not None and estate.ima_linked:
        if check_status.get('ima_container', False) or is_exited(
            schain_name, container_type=ContainerType.ima, dutils=dutils
        ):
            remove_ima_container(schain_name, dutils=dutils)
    if check_status['config_dir']:
        remove_config_dir(schain_name)
    mark_schain_deleted(schain_name)


def delete_bls_keys(skale, schain_name):
    last_rotation_id = skale.schains.last_rotation_id(schain_name)
    st = get_settings((SkaleSettings, FairSettings))
    for i in range(last_rotation_id + 1):
        try:
            secret_key_share_filepath = get_secret_key_share_filepath(schain_name, i)
            if os.path.isfile(secret_key_share_filepath):
                secret_key_share_config = read_json(secret_key_share_filepath) or {}
                bls_key_name = secret_key_share_config.get('key_share_name')
                if bls_key_name:
                    sgx = SgxClient(str(st.sgx_url), path_to_cert=str(SGX_CERTIFICATES_FOLDER))
                    sgx.delete_bls_key(bls_key_name)
        except Exception:
            logger.exception(f'Removing secret_key for rotation {i} failed')
