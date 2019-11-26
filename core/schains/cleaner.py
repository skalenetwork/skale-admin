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

from skale import Skale

from core.schains.checks import SChainChecks
from core.schains.helper import get_schain_dir_path
from core.schains.runner import get_container_name


from tools.docker_utils import DockerUtils
from tools.custom_thread import CustomThread
from tools.str_formatters import arguments_list_string
from tools.configs.web3 import ENDPOINT, ABI_FILEPATH
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER

from . import CLEANER_INTERVAL, MONITOR_INTERVAL


logger = logging.getLogger(__name__)
dutils = DockerUtils()


class SChainsCleaner():
    def __init__(self, skale, node_config):
        self.skale = skale
        self.node_config = node_config
        self.skale_events = Skale(ENDPOINT, ABI_FILEPATH)
        CustomThread('Wait for node ID', self.wait_for_node_id, once=True).start()

    def wait_for_node_id(self, opts):
        while not self.node_config.id:
            logger.debug('Waiting for the node_id in sChains Cleaner...')
            sleep(MONITOR_INTERVAL)
        self.node_id = self.node_config.id
        self.monitor = CustomThread('sChains cleaner monitor', self.schains_cleaner,
                                    interval=CLEANER_INTERVAL)
        self.monitor.start()

    def schains_cleaner(self, opts):
        schains_on_node = self.get_schains_on_node()
        schain_ids = self.schain_names_to_ids(schains_on_node)

        event_filter = self.skale_events.schains.contract.events.SchainDeleted.createFilter(
            fromBlock=0, argument_filters={'schainId': schain_ids})
        events = event_filter.get_all_entries()

        for event in events:
            name = event['args']['name']
            if name in schains_on_node:
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
            id = self.skale.schains_data.name_to_id(name)
            ids.append(bytes.fromhex(id))
        return ids

    def run_cleanup(self, schain_name):
        checks = SChainChecks(schain_name, self.node_id).get_all()
        if checks['container']:
            logger.warning(f'Going to remove container and volume for {schain_name}...')
            self.remove_schain_container(schain_name)
            dutils.rm_vol(schain_name)
        if checks['ima_container']:
            logger.warning(f'Going to remove IMA container for {schain_name}...')
            self.remove_ima_container(schain_name)
        if checks['data_dir']:
            logger.warning(f'Going to remove config folder for {schain_name}...')
            self.remove_config_folder(schain_name)

    def remove_schain_container(self, schain_name):
        schain_container_name = get_container_name(SCHAIN_CONTAINER, schain_name)
        return dutils.safe_rm(schain_container_name, v=True, force=True)

    def remove_ima_container(self, schain_name):
        ima_container_name = get_container_name(IMA_CONTAINER, schain_name)
        dutils.safe_rm(ima_container_name, v=True, force=True)

    def remove_config_folder(self, schain_name):
        schain_dir_path = get_schain_dir_path(schain_name)
        shutil.rmtree(schain_dir_path)
