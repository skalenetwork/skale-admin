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
import time

from core.schains.config import get_allowed_endpoints
from core.schains.helper import get_schain_dir_path, get_schain_config_filepath
from core.schains.runner import get_container_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.iptables import apsent_rules as apsent_iptables_rules

from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)
dutils = DockerUtils()


class SChainChecks:
    def __init__(self, skale, schain_name: str, node_id: int, log=False, failhook=None):
        self.name = schain_name
        self.node_id = node_id
        self.failhook = failhook
        self.skale = skale
        self.check_for_rotation()
        self.check_data_dir()
        self.check_config()
        self.check_dkg()
        self.check_volume()
        self.check_firewall_rules()
        self.check_container()
        self.check_ima_container()
        if log:
            self.log_health_check()
        if not self.is_healthy() and self.failhook:
            self.failhook(
                f'sChain checks failed: {self.name}, {self.get_all()}, node_id: {node_id}',
                level='warning')

    def check_data_dir(self):
        schain_dir_path = get_schain_dir_path(self.name)
        self._data_dir = {'result': os.path.isdir(schain_dir_path)}

    def check_dkg(self):
        secret_key_share_filepath = get_secret_key_share_filepath(self.name)
        self._dkg = {'result': os.path.isfile(secret_key_share_filepath)}

    def check_config(self):
        config_filepath = get_schain_config_filepath(self.name)
        self._config = {'result': os.path.isfile(config_filepath)}

    def check_volume(self):
        self._volume = {'result': dutils.data_volume_exists(self.name)}

    def check_container(self):
        name = get_container_name(SCHAIN_CONTAINER, self.name)
        info = dutils.get_info(name)
        self._container = {'result': dutils.container_running(info)}

    def check_ima_container(self):
        name = get_container_name(IMA_CONTAINER, self.name)
        info = dutils.get_info(name)
        self._ima_container = {'result': dutils.container_running(info)}

    def check_firewall_rules(self):
        self._firewall_rules = {'result': False}
        if self._config['result']:
            ips_ports = get_allowed_endpoints(self.name)
            self._firewall_rules['result'] = len(apsent_iptables_rules(ips_ports)) == 0

    def check_for_rotation(self):
        ts = time.time()
        rotation_data = self.skale.schains_data.get_rotation(self.name)
        finish_ts = rotation_data['finish_ts']
        rotation_in_progress = finish_ts > ts
        new_schain = rotation_data['new_node'] == self.node_id
        exiting_node = rotation_data['leaving_node'] == self.node_id
        self._rotation_in_progress = {
            'result': rotation_in_progress,
            'new_schain': new_schain,
            'exiting_node': exiting_node,
            'finish_ts': finish_ts
        }

    def is_healthy(self):
        checks = self.get_all()
        for check in checks:
            if not checks[check]:
                return False
        return True

    def get_all(self):
        return {
            'rotation_in_progress': self._rotation_in_progress,
            'data_dir': self._data_dir,
            'dkg': self._dkg,
            'config': self._config,
            'volume': self._volume,
            'container': self._container,
            'ima_container': self._ima_container,
            'firewall_rules': self._firewall_rules
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
            logger.info(
                arguments_list_string(
                    {'sChain name': self.name, 'Failed checks': failed_checks_str},
                    'Failed sChain checks', 'error'
                )
            )
