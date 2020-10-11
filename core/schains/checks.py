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

from core.schains.skaled_exit_codes import SkaledExitCodes
from core.schains.config.helper import get_allowed_endpoints, get_schain_rpc_ports
from core.schains.helper import get_schain_dir_path, get_schain_config_filepath
from core.schains.runner import get_container_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.iptables import apsent_rules as apsent_iptables_rules
from tools.helper import post_request

from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)
dutils = DockerUtils()


# TODO: Fix IMA
class SChainChecks:
    def __init__(self, schain_name: str, node_id: int, rotation_id=0, log=False, failhook=None):
        self.name = schain_name
        self.node_id = node_id
        self.failhook = failhook
        self.rotation_id = rotation_id

        self.container_name = get_container_name(SCHAIN_CONTAINER, self.name)
        self.info = dutils.get_info(self.container_name)

        self.run_checks()
        if log:
            self.log_health_check()
        if not self.is_healthy() and self.failhook:
            self.failhook(
                f'sChain checks failed: {self.name}, {self.get_all()}, node_id: {node_id}',
                level='warning')

    def run_checks(self):
        self.check_data_dir()
        self.check_config()
        self.check_dkg()
        self.check_volume()
        self.check_firewall_rules()
        self.check_container()
        self.check_broken_container()
        # self.check_ima_container()
        self.check_rpc()

    def check_data_dir(self):
        schain_dir_path = get_schain_dir_path(self.name)
        self._data_dir = os.path.isdir(schain_dir_path)

    def check_dkg(self):
        secret_key_share_filepath = get_secret_key_share_filepath(self.name, self.rotation_id)
        self._dkg = os.path.isfile(secret_key_share_filepath)

    def check_config(self):
        config_filepath = get_schain_config_filepath(self.name)
        self._config = os.path.isfile(config_filepath)

    def check_volume(self):
        self._volume = dutils.is_data_volume_exists(self.name)

    def check_container(self):
        self._container = dutils.container_running(self.info)

    def check_broken_container(self):
        exit_code = dutils.container_exit_code(self.info)
        self._needs_repair = int(exit_code) == SkaledExitCodes.EC_STATE_ROOT_MISMATCH.value

    def check_ima_container(self):
        name = get_container_name(IMA_CONTAINER, self.name)
        info = dutils.get_info(name)
        self._ima_container = dutils.container_running(info)

    def check_rpc(self):
        self._rpc = False
        if self._config:
            http_port, _ = get_schain_rpc_ports(self.name)
            http_endpoint = f'http://127.0.0.1:{http_port}'
            self._rpc = check_endpoint_alive(http_endpoint)

    def check_firewall_rules(self):
        self._firewall_rules = False
        if self._config:
            ips_ports = get_allowed_endpoints(self.name)
            self._firewall_rules = len(apsent_iptables_rules(ips_ports)) == 0

    def is_healthy(self):
        checks = self.get_all()
        return False not in checks.values()

    def get_all(self):
        return {
            'data_dir': self._data_dir,
            'dkg': self._dkg,
            'config': self._config,
            'volume': self._volume,
            'container': self._container,
            # TODO: Test IMA
            # 'ima_container': self._ima_container,
            'firewall_rules': self._firewall_rules,
            'rpc': self._rpc,
            'needs_repair': self._needs_repair
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


def get_rotation_state(skale, schain_name, node_id):
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    rotation_in_progress = skale.node_rotation.is_rotation_in_progress(schain_name)
    finish_ts = rotation_data['finish_ts']
    rotation_id = rotation_data['rotation_id']
    new_schain = rotation_data['new_node'] == node_id
    exiting_node = rotation_data['leaving_node'] == node_id
    return {
        'in_progress': rotation_in_progress,
        'new_schain': new_schain,
        'exiting_node': exiting_node,
        'finish_ts': finish_ts,
        'rotation_id': rotation_id
    }


def check_endpoint_alive(http_endpoint):
    res = post_request(
        http_endpoint,
        json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    )
    if res and res.status_code == 200:
        return True
    return False
