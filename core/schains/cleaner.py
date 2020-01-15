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
from time import sleep

from skale.manager_client import spawn_skale_lib

from core.schains.checks import SChainChecks
from core.schains.helper import get_schain_dir_path
from core.schains.runner import get_container_name

from tools.docker_utils import DockerUtils
from tools.custom_thread import CustomThread
from tools.str_formatters import arguments_list_string
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER

from . import CLEANER_INTERVAL, MONITOR_INTERVAL


logger = logging.getLogger(__name__)
dutils = DockerUtils()


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


class SChainsCleaner():
    def __init__(self, skale, node_config):
        self.skale = skale
        self.skale_events = spawn_skale_lib(skale)
        self.node_config = node_config
        CustomThread('Wait for node ID', self.wait_for_node_id, once=True).start()

    def wait_for_node_id(self, opts):
        while self.node_config.id is None:
            logger.debug('Waiting for the node_id in sChains Cleaner...')
            sleep(MONITOR_INTERVAL)
        self.node_id = self.node_config.id
        self.monitor = CustomThread('sChains cleaner monitor', self.schains_cleaner,
                                    interval=CLEANER_INTERVAL)
        self.monitor.start()
        logger.info(
            arguments_list_string({'Node ID': self.node_config.id}, 'sChains cleaner started'))

    def get_schain_names_from_contract(self):
        schains_on_contract = self.skale.schains_data.get_schains_for_node(self.node_config.id)
        return list(map(lambda schain: schain['name'], schains_on_contract))

    def schains_cleaner(self, opts):
        schains_on_node = self.get_schains_on_node()
        schain_ids = self.schain_names_to_ids(schains_on_node)
        schain_names_on_contracts = self.get_schain_names_from_contract()

        event_filter = self.skale_events.schains.contract.events.SchainDeleted.createFilter(
            fromBlock=0, argument_filters={'schainId': schain_ids})
        events = event_filter.get_all_entries()

        for event in events:
            name = event['args']['name']
            if name in schains_on_node and name not in schain_names_on_contracts:
                logger.info(
                    arguments_list_string({'sChain name': name}, 'sChain deleted event found'))
                self.run_cleanup(name)

    def get_schains_on_node(self):
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

    def schain_names_to_ids(self, schain_names):
        ids = []
        for name in schain_names:
            id_ = self.skale.schains_data.name_to_id(name)
            ids.append(bytes.fromhex(id_))
        return ids

    def run_cleanup(self, schain_name):
        checks = SChainChecks(schain_name, self.node_id).get_all()
        if checks['container']:
            remove_schain_container(schain_name)
        if checks['volume']:
            remove_schain_volume(schain_name)
        if checks['ima_container']:
            remove_ima_container(schain_name)
        if checks['data_dir']:
            remove_config_dir(schain_name)
