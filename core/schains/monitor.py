import os
import logging
from tools.custom_thread import CustomThread
from tools.config import DATA_DIR_CONTAINER_PATH

from sentry_sdk import capture_message

from core.schains.helper import init_schain_dir, get_schain_config_filepath
from core.schains.config import generate_schain_config, save_schain_config, \
    construct_runtime_args
from core.schains.volume import init_data_volume, get_container_limits
from core.schains.checks import SChainChecks
from core.schains.ima import construct_ima_runtime_args
# from core.schains_core.dkg import init_bls
from . import MONITOR_INTERVAL

from tools.config import MTA_CONFIG_NAME

logger = logging.getLogger(__name__)


class SchainsMonitor():
    def __init__(self, skale, wallet, docker_manager, node_id):
        self.skale = skale
        self.node_id = node_id
        self.wallet = wallet
        self.docker_manager = docker_manager
        self.monitor = CustomThread('sChains monitor', self.monitor_schains,
                                    interval=MONITOR_INTERVAL)
        self.monitor.start()

    def monitor_schains(self, opts):
        schains = self.skale.schains_data.get_schains_for_node(self.node_id)
        logger.info(f'Monitoring sChains for node_id: {self.node_id}, sChains on this node: {len(schains)}')  # todo: change to debug!

        threads = []
        for schain in schains:
            if not schain.get('name') or schain['name'] == '': continue
            schain_thread = CustomThread(f'sChain monitor: {schain["name"]}', self.monitor_schain,
                                         opts=schain, once=True)
            schain_thread.start()
            threads.append(schain_thread)

        for thread in threads:
            thread.join()

    def monitor_schain(self, schain):
        name = schain['name']
        checks = SChainChecks(name, self.node_id, self.docker_manager, log=True,
                              failhook=capture_message).get_all()

        if not checks['data_dir']:
            init_schain_dir(name)
        if not checks['config']:
            self.init_schain_config(name)
        # init_bls(self.skale.web3, self.wallet, name)
        if not checks['volume']:
            init_data_volume(schain)
        if not checks['container']:
            self.monitor_schain_container(name)
        if not checks['ima_container']:
            self.monitor_ima_container(name)

    def init_schain_config(self, schain_name):
        config_filepath = get_schain_config_filepath(schain_name)
        if not os.path.isfile(config_filepath):
            logger.warning(f'sChain config not found: {config_filepath}, trying to create.')
            schain_config = generate_schain_config(schain_name, self.node_id, self.skale)
            save_schain_config(schain_config, schain_name)

    def check_container(self, schain_name, volume_required=False):
        name = self.docker_manager.construct_schain_container_name(schain_name)
        info = self.docker_manager.get_info(name)
        if self.docker_manager.to_start_container(info):
            logger.warning(f'sChain container: {name} not found, trying to create.')
            if volume_required and not self.docker_manager.data_volume_exists(schain_name):
                logger.error(f'Cannot create sChain container without data volume - {schain_name}')
            return True

    def monitor_schain_container(self, schain_name):
        if self.check_container(schain_name, volume_required=True):
            self.run_schain_container(schain_name)

    def monitor_ima_container(self, schain_name):
        self.run_ima_container(schain_name)

    def run_schain_container(self, schain_name):
        runtime_args = construct_runtime_args(schain_name)
        schain = self.skale.schains_data.get_by_name(schain_name)
        cpu_limit, mem_limit = get_container_limits(schain)
        self.docker_manager.run_schain(schain_name, DATA_DIR_CONTAINER_PATH,
                                       runtime_args=runtime_args, cpu_limit=cpu_limit,
                                       mem_limit=mem_limit)

    def run_ima_container(self, schain_name):
        runtime_args = construct_ima_runtime_args(schain_name)
        mta_name = self.docker_manager.construct_mta_container_name(schain_name)
        self.docker_manager.run(MTA_CONFIG_NAME, container_name=mta_name,
                                custom_args=runtime_args)
