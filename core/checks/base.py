#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2025 SKALE Labs
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

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import statsd

from core.chain.rpc import (
    check_endpoint_alive,
    check_endpoint_blocks,
    get_endpoint_alive_check_timeout,
)
from core.chain.runner import get_container_name
from core.chain.skaled_exit_codes import SkaledExitCodes
from core.chain.volume import is_volume_exists
from core.config.endpoint import get_local_chain_http_endpoint_from_config
from core.config.schain.directory import get_schain_check_filepath
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.main import (
    get_skaled_config_rotations_ids,
    get_upstream_config_rotation_ids,
)
from core.firewall import IRuleController
from core.redis.chain_record import ChainRecord
from core.types.chain import ChainName
from tools.configs.containers import SKALED_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import no_hyphens, write_json
from tools.resources import get_statsd_client
from tools.str_formatters import arguments_list_string
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


API_ALLOWED_CHECKS = [
    'config_dir',
    'dkg',
    'config',
    'volume',
    'firewall_rules',
    'skaled_container',
    'exit_code_ok',
    'rpc',
    'blocks',
    'process',
    'ima_container',
]

TG_ALLOWED_CHECKS = [
    'volume',
    'firewall_rules',
    'skaled_container',
    'exit_code_ok',
    'rpc',
    'blocks',
    'process',
    'ima_container',
]


class CheckRes:
    def __init__(self, status: bool, data: dict | None = None):
        self.status = status
        self.data = data if data else {}

    def __bool__(self) -> bool:
        return self.status

    def __str__(self) -> str:
        return f'CheckRes<{self.status}>'


class IChecks(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    def get_all(
        self,
        log: bool = True,
        save: bool = False,
        expose: bool = False,
        needed: Optional[List[str]] = None,
    ) -> Dict:
        if needed:
            names = needed
        else:
            names = self.get_check_names()

        checks_status = {}
        for name in names:
            if hasattr(self, name):
                logger.debug('Running check %s', name)
                checks_status[name] = getattr(self, name).status
        if expose:
            send_to_statsd(self.statsd_client, self.get_name(), checks_status)  # type: ignore[attr-defined]
        if log:
            log_checks_dict(self.get_name(), checks_status)
        if save:
            save_checks_dict(self.get_name(), checks_status)
        return checks_status

    def is_healthy(self) -> bool:
        checks = self.get_all()
        return False not in checks.values()

    @classmethod
    def get_check_names(cls):
        return list(
            filter(
                lambda c: not c.startswith('_') and isinstance(getattr(cls, c), property), dir(cls)
            )
        )


class BaseSkaledChecks(IChecks):
    def __init__(
        self,
        chain_name: ChainName,
        chain_record: SChainRecord | ChainRecord,
        rule_controller: IRuleController,
        *,
        dutils: Optional[DockerUtils] = None,
        passive_node: bool = False,
    ):
        self.name = chain_name
        self.chain_record = chain_record
        self.dutils = dutils or DockerUtils()
        self.container_name = get_container_name(SKALED_CONTAINER, self.name)
        self.passive_node = passive_node
        self.rule_controller = rule_controller
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=chain_name)
        self.statsd_client = get_statsd_client()

    def get_name(self) -> str:
        return self.name

    @property
    def upstream_exists(self) -> CheckRes:
        return CheckRes(self.cfm.upstream_config_exists())

    @property
    def rotation_id_updated(self) -> CheckRes:
        if not self.config:
            return CheckRes(False)
        upstream_rotations = get_upstream_config_rotation_ids(self.cfm)
        config_rotations = get_skaled_config_rotations_ids(self.cfm)
        logger.debug(
            'Comparing rotation_ids. Upstream: %s. Config: %s', upstream_rotations, config_rotations
        )
        return CheckRes(upstream_rotations == config_rotations)

    @property
    def config_updated(self) -> CheckRes:
        if not self.config:
            return CheckRes(False)
        return CheckRes(self.cfm.skaled_config_synced_with_upstream())

    @property
    def config(self) -> CheckRes:
        """Checks that sChain config file exists"""
        return CheckRes(self.cfm.skaled_config_exists())

    @property
    def volume(self) -> CheckRes:
        """Checks that sChain volume exists"""

        return CheckRes(
            is_volume_exists(self.name, passive_node=self.passive_node, dutils=self.dutils)
        )

    @property
    def skaled_container(self) -> CheckRes:
        """Checks that skaled container is running"""
        return CheckRes(self.dutils.is_container_running(self.container_name))

    @property
    def exit_code_ok(self) -> CheckRes:
        """Checks that skaled exit code is OK"""
        exit_code = self.dutils.container_exit_code(self.container_name)
        res = int(exit_code) != SkaledExitCodes.EC_STATE_ROOT_MISMATCH
        return CheckRes(res)

    @property
    def rpc(self) -> CheckRes:
        """Checks that local skaled RPC is accessible"""
        res = False
        if self.config:
            config = self.cfm.skaled_config
            if not config:
                raise ValueError(
                    f'Config for sChain {self.name} is not found. '
                    'Please check if the chain is initialized.'
                )
            http_endpoint = get_local_chain_http_endpoint_from_config(config)
            timeout = get_endpoint_alive_check_timeout(self.chain_record.failed_rpc_count)
            res = check_endpoint_alive(http_endpoint, timeout=timeout)
        return CheckRes(res)

    @property
    def blocks(self) -> CheckRes:
        """Checks that local skaled is mining blocks"""
        if self.config:
            config = self.cfm.skaled_config
            if not config:
                raise ValueError(
                    f'Config for sChain {self.name} is not found. '
                    'Please check if the chain is initialized.'
                )
            http_endpoint = get_local_chain_http_endpoint_from_config(config)
            return CheckRes(check_endpoint_blocks(http_endpoint))
        return CheckRes(False)

    @property
    def exit_zero(self) -> CheckRes:
        """Check that sChain container exited with zero code"""
        if self.dutils.is_container_running(self.container_name):
            return CheckRes(False)
        exit_code = self.dutils.container_exit_code(self.container_name)
        return CheckRes(exit_code == SkaledExitCodes.EC_SUCCESS)


def get_api_checks_status(status: Dict, allowed: List = API_ALLOWED_CHECKS) -> Dict:
    return dict(filter(lambda r: r[0] in allowed, status.items()))


def save_checks_dict(schain_name, checks_dict):
    schain_check_path = get_schain_check_filepath(schain_name)
    logger.info(f'Saving checks for the chain {schain_name}: {schain_check_path}')
    try:
        write_json(schain_check_path, {'time': time.time(), 'checks': checks_dict})
    except Exception:
        logger.exception(f'Failed to save checks: {schain_check_path}')


def log_checks_dict(schain_name, checks_dict):
    logger.info(f'sChain {schain_name} checks: {checks_dict}')
    failed_checks = []
    for check in checks_dict:
        if not checks_dict[check]:
            failed_checks.append(check)
    if len(failed_checks) != 0:
        failed_checks_str = ', '.join(failed_checks)
        logger.info(
            arguments_list_string(
                {'sChain name': schain_name, 'Failed checks': failed_checks_str},
                'Failed sChain checks',
                'error',
            )
        )


def send_to_statsd(statsd_client: statsd.StatsClient, schain_name: str, checks_dict: dict) -> None:
    for check, result in checks_dict.items():
        mname = f'admin.schain_checks.{check}.{no_hyphens(schain_name)}'
        statsd_client.gauge(mname, int(result))
