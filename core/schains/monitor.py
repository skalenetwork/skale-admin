import os
import logging
from tools.custom_thread import CustomThread
from tools.docker_utils import DockerUtils

from sentry_sdk import capture_message

from core.schains.runner import run_schain_container, run_ima_container
from core.schains.helper import init_schain_dir, get_schain_config_filepath
from core.schains.config import generate_schain_config, save_schain_config, get_schain_env
from core.schains.volume import init_data_volume, get_container_limits
from core.schains.checks import SChainChecks
from core.schains.ima import get_ima_env
# from core.schains_core.dkg import init_bls

from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER

from . import MONITOR_INTERVAL

logger = logging.getLogger(__name__)
dutils = DockerUtils()


class SchainsMonitor():
    def __init__(self, skale, wallet, node_id):
        self.skale = skale
        self.node_id = node_id
        self.wallet = wallet
        self.monitor = CustomThread('sChains monitor', self.monitor_schains,
                                    interval=MONITOR_INTERVAL)
        self.monitor.start()

    def monitor_schains(self, opts):
        schains = self.skale.schains_data.get_schains_for_node(self.node_id)
        schains_on_node = len(schains)
        logger.info(
            f'Monitoring sChains for node_id: {self.node_id}, sChains on this node: {schains_on_node}')  # todo: change to debug!

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
        checks = SChainChecks(name, self.node_id, log=True, failhook=capture_message).get_all()

        if not checks['data_dir']:
            init_schain_dir(name)
        if not checks['config']:
            self.init_schain_config(name)
        # init_bls(self.skale.web3, self.wallet, name)
        #if not checks['volume']:
        #    init_data_volume(schain)
        if not checks['container']:
            self.monitor_schain_container(schain)
        if not checks['ima_container']:
            self.monitor_ima_container(schain)

    def init_schain_config(self, schain_name):
        config_filepath = get_schain_config_filepath(schain_name)
        if not os.path.isfile(config_filepath):
            logger.warning(f'sChain config not found: {config_filepath}, trying to create.')
            schain_config = generate_schain_config(schain_name, self.node_id, self.skale)
            save_schain_config(schain_config, schain_name)

    def check_container(self, schain_name, volume_required=False):
        name = get_container_name(SCHAIN_CONTAINER, schain_name)
        info = dutils.get_info(name)
        if dutils.to_start_container(info):
            logger.warning(f'sChain container: {name} not found, trying to create.')
            if volume_required and not dutils.data_volume_exists(schain_name):
                logger.error(f'Cannot create sChain container without data volume - {schain_name}')
            return True

    def monitor_schain_container(self, schain):
        if self.check_container(schain['name'], volume_required=True):
            env = get_schain_env(schain['name'])
            run_schain_container(schain, env)

    def monitor_ima_container(self, schain):
        env = get_ima_env(schain['name'])
        run_ima_container(schain, env)
