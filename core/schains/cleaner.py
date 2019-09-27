import os
import logging
import shutil

from core.schains.checks import SChainChecks
from core.schains.helper import get_schain_dir_path

from tools.config import SCHAINS_DIR_PATH
from tools.custom_thread import CustomThread
from tools.configs import LONG_LINE
from . import CLEANER_INTERVAL


logger = logging.getLogger(__name__)


class SChainsCleaner():
    def __init__(self, skale, docker_manager, docker_utils, node_id):
        self.skale = skale
        self.node_id = node_id
        self.docker_utils = docker_utils
        self.docker_manager = docker_manager
        self.monitor = CustomThread('sChains cleaner monitor', self.schains_cleaner,
                                    interval=CLEANER_INTERVAL)
        self.monitor.start()

    def schains_cleaner(self, opts):
        schains_on_node = self.get_schains_on_node()
        schain_ids = self.schain_names_to_ids(schains_on_node)

        event_filter = self.skale.schains.contract.events.SchainDeleted.createFilter(
            fromBlock=0, argument_filters={'schainId': schain_ids})
        events = event_filter.get_all_entries()

        for event in events:
            name = event['args']['name']
            if name in schains_on_node:
                logger.warning(
                    f'\n{LONG_LINE}\nFound SchainDeleted event for: {name}, going to run cleanup...\n{LONG_LINE}')
                self.run_cleanup(name)

    def get_schains_on_node(self):
        # get all schain dirs
        schain_dirs = os.listdir(SCHAINS_DIR_PATH)
        # get all schain containers
        schain_containers = self.docker_utils.get_all_schain_containers(all=True)
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
        checks = SChainChecks(schain_name, self.node_id, self.docker_manager).get_all()
        if checks['container']:
            logger.warning(f'Going to remove container and volume for {schain_name}...')
            self.remove_schain_container(schain_name)
            self.docker_manager.rm_vol(schain_name)
        if checks['ima_container']:
            logger.warning(f'Going to remove IMA container for {schain_name}...')
            self.remove_ima_container(schain_name)
        if checks['data_dir']:
            logger.warning(f'Going to remove config folder for {schain_name}...')
            self.remove_config_folder(schain_name)

    def remove_schain_container(self, schain_name):
        schain_container_name = self.docker_manager.construct_schain_container_name(schain_name)
        return self.docker_manager.safe_rm(schain_container_name, v=True, force=True)

    def remove_ima_container(self, schain_name):
        ima_container_name = self.docker_manager.construct_mta_container_name(schain_name)
        self.docker_manager.safe_rm(ima_container_name, v=True, force=True)

    def remove_config_folder(self, schain_name):
        schain_dir_path = get_schain_dir_path(schain_name)
        shutil.rmtree(schain_dir_path)
