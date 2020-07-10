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
import logging
import shutil
from multiprocessing import Process


from core.schains.checks import SChainChecks
from core.schains.helper import get_schain_dir_path
from core.schains.runner import get_container_name, check_container_exit
from core.schains.config import get_allowed_endpoints

from sgx import SgxClient

from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.configs import SGX_CERTIFICATES_FOLDER
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from tools.docker_utils import DockerUtils
from tools.iptables import remove_rules as remove_iptables_rules
from tools.helper import read_json
from tools.str_formatters import arguments_list_string
from web.models.schain import mark_schain_deleted


logger = logging.getLogger(__name__)
dutils = DockerUtils()


def run_cleaner(skale, node_config):
    process = Process(target=monitor, args=(skale, node_config))
    process.start()
    process.join()


def log_remove(component_name, schain_name):
    logger.warning(f'Going to remove {component_name} for sChain {schain_name}')


def remove_schain_volume(schain_name):
    log_remove('volume', schain_name)
    dutils.rm_vol(schain_name)


def remove_schain_container(schain_name):
    log_remove('container', schain_name)
    schain_container_name = get_container_name(SCHAIN_CONTAINER, schain_name)
    return dutils.safe_rm(schain_container_name, v=True, force=True)


def remove_ima_container(schain_name):
    log_remove('IMA container', schain_name)
    ima_container_name = get_container_name(IMA_CONTAINER, schain_name)
    dutils.safe_rm(ima_container_name, v=True, force=True)


def remove_config_dir(schain_name):
    log_remove('config directory', schain_name)
    schain_dir_path = get_schain_dir_path(schain_name)
    shutil.rmtree(schain_dir_path)


def monitor(skale, node_config):
    logger.info('Cleaner procedure started.')
    schains_on_node = get_schains_on_node()
    schain_names_on_contracts = get_schain_names_from_contract(skale,
                                                               node_config.id)
    for schain_name in schains_on_node:
        on_contract = schain_name in schain_names_on_contracts
        if not on_contract and (
            not skale.schains_internal.is_schain_exist(schain_name) or
                check_container_exit(schain_name, dutils=dutils)):
            logger.info(
                arguments_list_string({'sChain name': schain_name},
                                      'Removed sChain found'))
            last_rotation_id = skale.schains.get_last_rotation_id(schain_name)
            for i in range(last_rotation_id + 1):
                try:
                    secret_key_share_filepath = get_secret_key_share_filepath(
                                                                    schain_name, last_rotation_id
                                                                            )
                    secret_key_share_config = read_json(secret_key_share_filepath)
                    bls_key_name = secret_key_share_config['key_share_name']
                    sgx = SgxClient(os.environ['SGX_SERVER_URL'],
                                    path_to_cert=SGX_CERTIFICATES_FOLDER
                                    )
                    sgx.delete_bls_key(bls_key_name)
                except IOError:
                    continue
            cleanup_schain(node_config.id, schain_name)
        logger.info('Cleanup procedure finished')


def get_schain_names_from_contract(skale, node_id):
    schains_on_contract = skale.schains.get_schains_for_node(node_id)
    return list(map(lambda schain: schain['name'], schains_on_contract))


def get_schains_on_node():
    # get all schain dirs
    schain_dirs = os.listdir(SCHAINS_DIR_PATH)
    # get all schain containers
    schain_containers = dutils.get_all_schain_containers(all=True)
    schain_containers_names = []
    for container in schain_containers:
        schain_name = container.name.replace('skale_schain_', '', 1)
        schain_containers_names.append(schain_name)
    # merge 2 lists without duplicates
    return list(set(schain_dirs + schain_containers_names))


def schain_names_to_ids(skale, schain_names):
    ids = []
    for name in schain_names:
        id_ = skale.schains.name_to_id(name)
        ids.append(bytes.fromhex(id_))
    return ids


def remove_firewall_rules(schain_name):
    endpoints = get_allowed_endpoints(schain_name)
    remove_iptables_rules(endpoints)


def cleanup_schain(node_id, schain_name):
    checks = SChainChecks(schain_name, node_id).get_all()
    if checks['container'] or check_container_exit(schain_name, dutils=dutils):
        remove_schain_container(schain_name)
    if checks['volume']:
        remove_schain_volume(schain_name)
    if checks['firewall_rules']:
        remove_firewall_rules(schain_name)
    # TODO: Test IMA
    # if checks['ima_container']:
    #     remove_ima_container(schain_name)
    if checks['data_dir']:
        remove_config_dir(schain_name)
    mark_schain_deleted(schain_name)
