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
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from core.schains.config.directory import get_schain_check_filepath
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config,
    get_local_schain_http_endpoint_from_config
)
from core.schains.config.main import (
    get_skaled_config_rotations_ids,
    get_upstream_config_rotation_ids
)
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.firewall.types import IRuleController
from core.schains.ima import get_migration_ts as get_ima_migration_ts
from core.schains.process_manager_helper import is_monitor_process_alive
from core.schains.rpc import (
    check_endpoint_alive,
    check_endpoint_blocks,
    get_endpoint_alive_check_timeout
)
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.runner import get_container_name, get_image_name, is_new_image_pulled
from core.schains.skaled_exit_codes import SkaledExitCodes

from tools.configs.containers import IMA_CONTAINER, NO_CONTAINERS, SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import write_json
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
    'ima_container'
]


class CheckRes:
    def __init__(self, status: bool, data: dict = None):
        self.status = status
        self.data = data if data else {}

    def __bool__(self) -> bool:
        return self.status

    def __str__(self) -> str:
        return f'CheckRes<{self.status}>'


class IChecks(ABC):
    @abstractmethod
    def get_all(self, log=True, save=False, checks_filter=None) -> Dict:
        pass

    def is_healthy(self) -> bool:
        checks = self.get_all()
        return False not in checks.values()

    @classmethod
    def get_check_names(cls):
        return list(filter(
            lambda c: not c.startswith('_') and isinstance(
                getattr(cls, c), property),
            dir(cls)
        ))


class ConfigChecks(IChecks):
    def __init__(
        self,
        schain_name: str,
        node_id: int,
        schain_record: SChainRecord,
        rotation_id: int,
        stream_version: str,
        estate: ExternalState,
        econfig: Optional[ExternalConfig] = None
    ):
        self.name = schain_name
        self.node_id = node_id
        self.schain_record = schain_record
        self.rotation_id = rotation_id
        self.stream_version = stream_version
        self.estate = estate
        self.econfig = econfig or ExternalConfig(schain_name)
        self.cfm: ConfigFileManager = ConfigFileManager(
            schain_name=schain_name
        )

    def get_all(self, log=True, save=False, checks_filter=None) -> Dict:
        if checks_filter:
            names = checks_filter
        else:
            names = self.get_check_names()

        checks_dict = {}
        for name in names:
            if hasattr(self, name):
                checks_dict[name] = getattr(self, name).status
        if log:
            log_checks_dict(self.name, checks_dict)
        if save:
            save_checks_dict(self.name, checks_dict)
        return checks_dict

    @property
    def config_dir(self) -> CheckRes:
        """Checks that sChain config directory exists"""
        dir_path = self.cfm.dirname
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
    def upstream_config(self) -> CheckRes:
        """Checks that config exists for rotation id and stream"""
        exists = self.cfm.upstream_exist_for_rotation_id(self.rotation_id)

        logger.debug('Upstream configs status for %s: %s', self.name, exists)
        return CheckRes(
            exists and
            self.schain_record.config_version == self.stream_version and
            not self.schain_record.sync_config_run
        )

    @property
    def external_state(self) -> CheckRes:
        actual_state = self.econfig.get()
        logger.debug(
            'Checking external config. Current %s. Saved %s',
            self.estate, actual_state
        )
        return CheckRes(self.econfig.synced(self.estate))


class SkaledChecks(IChecks):
    def __init__(
        self,
        schain_name: str,
        schain_record: SChainRecord,
        rule_controller: IRuleController,
        *,
        econfig: Optional[ExternalConfig] = None,
        dutils: DockerUtils = None
    ):
        self.name = schain_name
        self.schain_record = schain_record
        self.dutils = dutils or DockerUtils()
        self.container_name = get_container_name(SCHAIN_CONTAINER, self.name)
        self.econfig = econfig or ExternalConfig(name=schain_name)
        self.rc = rule_controller
        self.cfm: ConfigFileManager = ConfigFileManager(
            schain_name=schain_name
        )

    def get_all(self, log=True, save=False, checks_filter=None) -> Dict:
        if checks_filter:
            names = checks_filter
        else:
            names = self.get_check_names()

        checks_dict = {}
        for name in names:
            if hasattr(self, name):
                checks_dict[name] = getattr(self, name).status
        if log:
            log_checks_dict(self.name, checks_dict)
        if save:
            save_checks_dict(self.name, checks_dict)
        return checks_dict

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
            'Comparing rotation_ids. Upstream: %s. Config: %s',
            upstream_rotations,
            config_rotations
        )
        return CheckRes(upstream_rotations == config_rotations)

    @property
    def config_updated(self) -> CheckRes:
        if not self.config:
            return CheckRes(False)
        return CheckRes(self.cfm.skaled_config_synced_with_upstream())

    @property
    def config(self) -> CheckRes:
        """ Checks that sChain config file exists """
        return CheckRes(self.cfm.skaled_config_exists())

    @property
    def volume(self) -> CheckRes:
        """Checks that sChain volume exists"""
        return CheckRes(self.dutils.is_data_volume_exists(self.name))

    @property
    def firewall_rules(self) -> CheckRes:
        """Checks that firewall rules are set correctly"""
        if self.config:
            conf = self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)
            ranges = self.econfig.ranges
            self.rc.configure(
                base_port=base_port,
                own_ip=own_ip,
                node_ips=node_ips,
                sync_ip_ranges=ranges
            )
            logger.debug(f'Rule controller {self.rc.expected_rules()}')
            return CheckRes(self.rc.is_rules_synced())
        return CheckRes(False)

    @property
    def skaled_container(self) -> CheckRes:
        """Checks that skaled container is running"""
        # todo: modify check!
        return NO_CONTAINERS or self.dutils.is_container_running(self.container_name)

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
        if not self.econfig.ima_linked:
            return CheckRes(True)
        container_name = get_container_name(IMA_CONTAINER, self.name)
        new_image_pulled = is_new_image_pulled(
            type=IMA_CONTAINER, dutils=self.dutils)

        migration_ts = get_ima_migration_ts(self.name)
        new = time.time() > migration_ts

        container_running = self.dutils.is_container_running(container_name)

        updated_image = False
        if container_running:
            expected_image = get_image_name(type=IMA_CONTAINER, new=new)
            image = self.dutils.get_container_image_name(container_name)
            updated_image = image == expected_image

        data = {
            'container_running': container_running,
            'updated_image': updated_image,
            'new_image_pulled': new_image_pulled
        }
        logger.debug(
            '%s, IMA check - %s',
            self.name, data
        )
        result: bool = container_running and updated_image and new_image_pulled
        return CheckRes(result, data=data)

    @property
    def rpc(self) -> CheckRes:
        """Checks that local skaled RPC is accessible"""
        res = False
        if self.config:
            config = self.cfm.skaled_config
            http_endpoint = get_local_schain_http_endpoint_from_config(config)
            timeout = get_endpoint_alive_check_timeout(
                self.schain_record.failed_rpc_count
            )
            res = check_endpoint_alive(http_endpoint, timeout=timeout)
        return CheckRes(res)

    @property
    def blocks(self) -> CheckRes:
        """Checks that local skaled is mining blocks"""
        if self.config:
            config = self.cfm.skaled_config
            http_endpoint = get_local_schain_http_endpoint_from_config(config)
            return CheckRes(check_endpoint_blocks(http_endpoint))
        return CheckRes(False)

    @property
    def process(self) -> CheckRes:
        """Checks that sChain monitor process is running"""
        return CheckRes(is_monitor_process_alive(self.schain_record.monitor_id))

    @property
    def exit_zero(self) -> CheckRes:
        """Check that sChain container exited with zero code"""
        if self.dutils.is_container_running(self.container_name):
            return CheckRes(False)
        exit_code = self.dutils.container_exit_code(self.container_name)
        return CheckRes(exit_code == SkaledExitCodes.EC_SUCCESS)


class SChainChecks(IChecks):
    def __init__(
        self,
        schain_name: str,
        node_id: int,
        schain_record: SChainRecord,
        rule_controller: IRuleController,
        stream_version: str,
        estate: ExternalState,
        rotation_id: int = 0,
        *,
        econfig: Optional[ExternalConfig] = None,
        dutils: DockerUtils = None
    ):
        self._subjects = [
            ConfigChecks(
                schain_name=schain_name,
                node_id=node_id,
                schain_record=schain_record,
                rotation_id=rotation_id,
                stream_version=stream_version,
                estate=estate,
                econfig=econfig
            ),
            SkaledChecks(
                schain_name=schain_name,
                schain_record=schain_record,
                rule_controller=rule_controller,
                econfig=econfig,
                dutils=dutils
            )
        ]

    def __getattr__(self, attr: str) -> Any:
        for subj in self._subjects:
            if attr in dir(subj):
                return getattr(subj, attr)
        raise AttributeError(f'No such attribute {attr}')

    def get_all(self, log=True, save=False, checks_filter=None):
        if not checks_filter:
            checks_filter = API_ALLOWED_CHECKS

        plain_checks = {}
        for subj in self._subjects:
            subj_checks = subj.get_all(
                log=False,
                save=False,
                checks_filter=checks_filter
            )
            plain_checks.update(subj_checks)
        if not self.estate.ima_linked:
            if 'ima_container' in plain_checks:
                del plain_checks['ima_container']

        if log:
            log_checks_dict(self.name, plain_checks)
        if save:
            save_checks_dict(self.name, plain_checks)
        return plain_checks


def save_checks_dict(schain_name, checks_dict):
    schain_check_path = get_schain_check_filepath(schain_name)
    logger.info(
        f'Saving checks for the chain {schain_name}: {schain_check_path}')
    try:
        write_json(schain_check_path, {
            'time': time.time(),
            'checks': checks_dict
        })
    except Exception:
        logger.exception(f'Failed to save checks: {schain_check_path}')


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
