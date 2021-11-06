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
from typing import Callable

from core.schains.skaled_exit_codes import SkaledExitCodes
from core.schains.rpc import check_endpoint_alive, check_endpoint_blocks
from core.schains.config.generator import schain_config_version_match
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_local_schain_http_endpoint
)
from core.schains.config.directory import (
    get_schain_config,
    schain_config_dir,
    schain_config_filepath
)
from core.schains.runner import get_container_name
from core.schains.dkg.utils import get_secret_key_share_filepath
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.configs.ima import DISABLE_IMA

from tools.docker_utils import DockerUtils
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


class CheckRes:
    def __init__(self, status: bool, data: dict = None):
        self.status = status
        self.data = data if data else {}


class SChainChecks:
    def __init__(
        self,
        schain_name: str,
        node_id: int,
        schain_record: SChainRecord,
        rule_controller_creator: Callable,
        rotation_id: int = 0,
        *,
        ima_linked: bool = True,
        dutils: DockerUtils = None
    ):
        self.name = schain_name
        self.node_id = node_id
        self.schain_record = schain_record
        self.rotation_id = rotation_id
        self.dutils = dutils or DockerUtils()
        self.container_name = get_container_name(SCHAIN_CONTAINER, self.name)
        self.ima_linked = ima_linked
        self.rc_creator = rule_controller_creator

    @property
    def config_dir(self) -> CheckRes:
        """Checks that sChain config directory exists"""
        dir_path = schain_config_dir(self.name)
        return CheckRes(os.path.isdir(dir_path))

    @property
    def dkg(self) -> CheckRes:
        """Checks that DKG procedure is completed"""
        secret_key_share_filepath = get_secret_key_share_filepath(
            self.name,
            self.rotation_id
        )
        return CheckRes(os.path.isfile(secret_key_share_filepath))

    @property
    def config(self) -> CheckRes:
        """Checks that sChain config file exists"""
        config_filepath = schain_config_filepath(self.name)
        if not os.path.isfile(config_filepath):
            return CheckRes(False)
        return CheckRes(
            schain_config_version_match(self.name, self.schain_record)
        )

    @property
    def volume(self) -> CheckRes:
        """Checks that sChain volume exists"""
        return CheckRes(self.dutils.is_data_volume_exists(self.name))

    @property
    def firewall_rules(self) -> CheckRes:
        """Checks that firewall rules are set correctly"""
        if self.config:
            conf = get_schain_config(self.name)
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)
            rc = self.rc_creator(
                name=self.name,
                base_port=base_port,
                own_ip=own_ip,
                node_ips=node_ips
            )
            return CheckRes(rc.is_rules_synced())
        return CheckRes(False)

    @property
    def skaled_container(self) -> CheckRes:
        """Checks that skaled container is running"""
        # todo: modify check!
        return CheckRes(self.dutils.is_container_running(self.container_name))

    @property
    def exit_code_ok(self) -> CheckRes:
        """Checks that skaled exit code is OK"""
        # todo: modify check!
        exit_code = self.dutils.container_exit_code(self.container_name)
        res = int(exit_code) != SkaledExitCodes.EC_STATE_ROOT_MISMATCH
        return CheckRes(res)

    @property
    def ima_container(self) -> CheckRes:
        """Checks that IMA container is running"""
        name = get_container_name(IMA_CONTAINER, self.name)
        return CheckRes(self.dutils.is_container_running(name))

    @property
    def rpc(self) -> CheckRes:
        """Checks that local skaled RPC is accessible"""
        res = False
        if self.config:
            http_endpoint = get_local_schain_http_endpoint(self.name)
            res = check_endpoint_alive(http_endpoint)
        return CheckRes(res)

    @property
    def blocks(self) -> CheckRes:
        """Checks that local skaled is mining blocks"""
        if self.config:
            http_endpoint = get_local_schain_http_endpoint(self.name)
            return CheckRes(check_endpoint_blocks(http_endpoint))
        return CheckRes(False)

    def get_all(self, log=True):
        checks_dict = {
            'data_dir': self.config_dir.status,
            'dkg': self.dkg.status,
            'config': self.config.status,
            'volume': self.volume.status,
            'firewall_rules': self.firewall_rules.status,
            'container': self.skaled_container.status,
            'exit_code_ok': self.exit_code_ok.status,
            'rpc': self.rpc.status,
            'blocks': self.blocks.status
        }
        if not DISABLE_IMA and self.ima_linked:
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
