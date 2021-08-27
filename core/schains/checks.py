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
from core.schains.rpc import check_endpoint_alive, check_endpoint_blocks
from core.schains.config.generator import schain_config_version_match
from core.schains.config.helper import (
    get_allowed_endpoints,
    get_local_schain_http_endpoint
)
from core.schains.helper import get_schain_dir_path, get_schain_config_filepath
from core.schains.runner import get_container_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.configs.ima import DISABLE_IMA
from tools.iptables import apsent_rules as apsent_iptables_rules

from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string

logger = logging.getLogger(__name__)


class SChainChecks:
    def __init__(
        self,
        schain_name: str,
        node_id: int,
        rotation_id: int = 0,
        *,
        dutils: DockerUtils = None
    ):
        self.name = schain_name
        self.node_id = node_id
        self.rotation_id = rotation_id
        self.dutils = dutils or DockerUtils()
        self.container_name = get_container_name(SCHAIN_CONTAINER, self.name)

    @property
    def data_dir(self) -> bool:
        """Checks that sChain data dir exists"""
        schain_dir_path = get_schain_dir_path(self.name)
        return os.path.isdir(schain_dir_path)

    @property
    def dkg(self) -> bool:
        """Checks that DKG procedure is completed"""
        secret_key_share_filepath = get_secret_key_share_filepath(
            self.name,
            self.rotation_id
        )
        return os.path.isfile(secret_key_share_filepath)

    @property
    def config(self) -> bool:
        """Checks that sChain config file exists"""
        config_filepath = get_schain_config_filepath(self.name)
        if not os.path.isfile(config_filepath):
            return False
        return schain_config_version_match(self.name)

    @property
    def volume(self) -> bool:
        """Checks that sChain volume exists"""
        return self.dutils.is_data_volume_exists(self.name)

    @property
    def firewall_rules(self) -> bool:
        """Checks that firewall rules are setted correctly"""
        if self.config:
            ips_ports = get_allowed_endpoints(self.name)
            return len(apsent_iptables_rules(ips_ports)) == 0
        return False

    @property
    def container(self) -> bool:
        """Checks that skaled container is running"""
        return self.dutils.is_container_running(self.container_name)

    @property
    def exit_code_ok(self) -> bool:
        """Checks that skaled exit code is OK"""
        exit_code = self.dutils.container_exit_code(self.container_name)
        return int(exit_code) != SkaledExitCodes.EC_STATE_ROOT_MISMATCH

    @property
    def ima_container(self) -> bool:
        """Checks that IMA container is running"""
        name = get_container_name(IMA_CONTAINER, self.name)
        return self.dutils.is_container_running(name)

    @property
    def rpc(self) -> bool:
        """Checks that local skaled RPC is accessible"""
        if self.config:
            http_endpoint = get_local_schain_http_endpoint(self.name)
            return check_endpoint_alive(http_endpoint)
        return False

    @property
    def blocks(self) -> bool:
        """Checks that local skaled is mining blocks"""
        if self.config:
            http_endpoint = get_local_schain_http_endpoint(self.name)
            return check_endpoint_blocks(http_endpoint)
        return False

    def get_all(self, log=True):
        checks_dict = {
            'data_dir': self.data_dir,
            'dkg': self.dkg,
            'config': self.config,
            'volume': self.volume,
            'firewall_rules': self.firewall_rules,
            'container': self.container,
            'exit_code_ok': self.exit_code_ok,
            'rpc': self.rpc,
            'blocks': self.blocks
        }
        if not DISABLE_IMA:
            checks_dict['ima_container'] = self.ima_container
        if log:
            log_checks_dict(self.name, checks_dict)
        return checks_dict

    def is_healthy(self):
        checks = self.get_all()
        return False not in checks.values()


def log_checks_dict(schain_name, checks_dict):
    logger.info(f'sChain {schain_name} checks: {checks_dict}')
    failed_checks = []
    for check in checks_dict:
        if not checks_dict[check]:
            failed_checks.append(check)
    if len(failed_checks) != 0:
        failed_checks_str = ", ".join(failed_checks)
        logger.info(
            arguments_list_string(
                {
                    'sChain name': schain_name,
                    'Failed checks': failed_checks_str
                },
                'Failed sChain checks', 'error'
            )
        )
