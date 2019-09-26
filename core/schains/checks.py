import os
import logging

from core.schains.helper import get_schain_dir_path, get_schain_config_filepath

from tools.docker_utils import DockerUtils
from tools.configs import LONG_LINE


logger = logging.getLogger(__name__)
docker_utils = DockerUtils()

class SChainChecks():
    def __init__(self, schain_name: str, node_id: int, docker_manager, log=False, failhook=None):
        self.name = schain_name
        self.node_id = node_id
        self.docker_manager = docker_manager
        self.failhook = failhook
        self.check_data_dir()
        self.check_config()
        self.check_volume()
        self.check_container()
        self.check_ima_container()
        if log: self.log_health_check()
        if not self.is_healthy() and self.failhook: self.failhook(
            f'sChain checks failed: {self.name}, {self.get_all()}, node_id: {node_id}',
            level='warning')

    def check_data_dir(self):
        schain_dir_path = get_schain_dir_path(self.name)
        self._data_dir = os.path.isdir(schain_dir_path)

    def check_config(self):
        config_filepath = get_schain_config_filepath(self.name)
        self._config = os.path.isfile(config_filepath)

    def check_volume(self):
        self._volume = docker_utils.data_volume_exists(self.name)

    def check_container(self):
        name = self.docker_manager.construct_schain_container_name(self.name)
        info = self.docker_manager.get_info(name)
        self._container = self.docker_manager.container_running(info)

    def check_ima_container(self):
        name = self.docker_manager.construct_mta_container_name(self.name)
        info = self.docker_manager.get_info(name)
        self._ima_container = self.docker_manager.container_running(info)

    def is_healthy(self):
        checks = self.get_all()
        for check in checks:
            if not checks[check]:
                return False
        return True

    def get_all(self):
        return {
            'data_dir': self._data_dir,
            'config': self._config,
            'volume': self._volume,
            'container': self._container,
            'ima_container': self._ima_container,
        }

    def log_health_check(self):
        checks = self.get_all()
        logger.info(f'sChain {self.name} checks: {checks}')
        failed_checks = []
        for check in checks:
            if not checks[check]:
                failed_checks.append(check)
        if len(failed_checks) != 0:
            failed_checks_str = ", ".join(failed_checks)
            logger.warning(
                f'\n{LONG_LINE}\n SOME CHECKS FOR SCHAIN {self.name} failed: \n {failed_checks_str} \n{LONG_LINE}')
