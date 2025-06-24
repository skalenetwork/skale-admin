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
import os
import time
from typing import Any, List, Optional

from skale.types.schain import SchainName

from core.chain.runner import (
    get_container_name,
    get_ima_container_time_frame,
    get_image_name,
    is_new_image_pulled,
)
from core.checks.base import (
    API_ALLOWED_CHECKS,
    BaseSkaledChecks,
    CheckRes,
    IChecks,
    log_checks_dict,
    save_checks_dict,
)
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.helper import (
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.config.utils import get_base_port_from_config
from core.firewall import IRuleController
from core.node import ExtendedManagerNodeInfo, get_current_ips
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.ima import get_ima_time_frame
from core.schains.ima import get_migration_ts as get_ima_migration_ts
from tools.configs.containers import IMA_CONTAINER
from tools.docker_utils import DockerUtils
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord

logger = logging.getLogger(__name__)


class ConfigChecks(IChecks):
    def __init__(
        self,
        schain_name: str,
        node_id: int,
        schain_record: SChainRecord,
        rotation_id: int,
        stream_version: str,
        current_nodes: list[ExtendedManagerNodeInfo],
        estate: ExternalState,
        last_dkg_successful: bool,
        sync_node: bool = False,
        econfig: Optional[ExternalConfig] = None,
    ) -> None:
        self.name = schain_name
        self.node_id = node_id
        self.schain_record = schain_record
        self.rotation_id = rotation_id
        self.stream_version = stream_version
        self.current_nodes = current_nodes
        self.estate = estate
        self._last_dkg_successful = last_dkg_successful
        self.sync_node = sync_node
        self.econfig = econfig or ExternalConfig(schain_name)
        self.cfm: ConfigFileManager = ConfigFileManager(chain_name=schain_name)
        self.statsd_client = get_statsd_client()

    def get_name(self) -> str:
        return self.name

    @property
    def config_dir(self) -> CheckRes:
        """Checks that sChain config directory exists"""
        dir_path = self.cfm.dirname
        return CheckRes(os.path.isdir(dir_path))

    @property
    def last_dkg_successful(self) -> CheckRes:
        """Checks that last dkg was successfuly completed"""
        return CheckRes(self._last_dkg_successful)

    @property
    def dkg(self) -> CheckRes:
        """Checks that DKG procedure is completed"""
        secret_key_share_filepath = get_secret_key_share_filepath(self.name, self.rotation_id)
        return CheckRes(os.path.isfile(secret_key_share_filepath))

    @property
    def skaled_node_ips(self) -> CheckRes:
        """Checks that IP list on the skale-manager is the same as in the skaled config"""
        res = False
        if self.cfm.skaled_config_exists():
            conf = self.cfm.skaled_config
            node_ips = get_node_ips_from_config(conf)
            current_ips = get_current_ips(self.current_nodes)
            res = set(node_ips) == set(current_ips)
        return CheckRes(res)

    @property
    def upstream_config(self) -> CheckRes:
        """
        Returns True if config exists for current rotation id,
        node ip addresses and stream version are up to date
        and config regeneration was not triggered manually.
        Returns False otherwise.
        """
        exists = self.cfm.upstream_exist_for_rotation_id(self.rotation_id)
        logger.debug('Upstream configs status for %s: %s', self.name, exists)
        stream_updated = self.schain_record.config_version == self.stream_version
        node_ips_updated = True
        triggered = self.schain_record.sync_config_run
        if exists:
            conf = self.cfm.latest_upstream_config
            upstream_node_ips = get_node_ips_from_config(conf)
            current_ips = get_current_ips(self.current_nodes)
            node_ips_updated = set(upstream_node_ips) == set(current_ips)

        logger.info(
            'Upstream config status, rotation_id %s: exist: %s, ips: %s, stream: %s, triggered: %s',
            self.rotation_id,
            exists,
            node_ips_updated,
            stream_updated,
            triggered,
        )
        return CheckRes(exists and node_ips_updated and stream_updated and not triggered)

    @property
    def external_state(self) -> CheckRes:
        actual_state = self.econfig.get()
        logger.debug('Checking external config. Current %s. Saved %s', self.estate, actual_state)
        return CheckRes(self.econfig.synced(self.estate))


class SkaledChecks(BaseSkaledChecks):
    def __init__(
        self,
        schain_name: SchainName,
        schain_record: SChainRecord,
        rule_controller: IRuleController,
        *,
        econfig: Optional[ExternalConfig] = None,
        dutils: Optional[DockerUtils] = None,
        sync_node: bool = False,
    ):
        self.econfig = econfig or ExternalConfig(name=schain_name)
        super().__init__(
            chain_name=schain_name,
            chain_record=schain_record,
            rule_controller=rule_controller,
            dutils=dutils,
            sync_node=sync_node,
        )

    @property
    def firewall_rules(self) -> CheckRes:
        """Checks that firewall rules are set correctly"""
        data = {
            'inited': False,
            'rules': False,
            'persistent': False,
        }
        if self.config:
            conf = self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)
            ranges = self.econfig.ranges
            self.rule_controller.configure(
                base_port=base_port, own_ip=own_ip, node_ips=node_ips, sync_ip_ranges=ranges
            )
            logger.debug(f'Rule controller {self.rule_controller.expected_rules()}')
            data.update(
                {
                    'inited': self.rule_controller.is_inited(),
                    'rules': self.rule_controller.is_rules_synced(),
                    'persistent': self.rule_controller.is_persistent(),
                }
            )
            logger.debug('Firewall rules check: %s', data)
            status = all(data.values())
            return CheckRes(status=status, data=data)
        return CheckRes(status=False, data=data)

    @property
    def ima_container(self) -> CheckRes:
        """Checks that IMA container is running"""
        if not self.econfig.ima_linked:
            return CheckRes(True)
        container_name = get_container_name(IMA_CONTAINER, self.name)
        new_image_pulled = is_new_image_pulled(image_type=IMA_CONTAINER, dutils=self.dutils)

        migration_ts = get_ima_migration_ts(self.name)
        after = time.time() > migration_ts

        container_running = self.dutils.is_container_running(container_name)

        updated_image, updated_time_frame = False, False
        if container_running:
            expected_image = get_image_name(image_type=IMA_CONTAINER, new=after)
            image = self.dutils.get_container_image_name(container_name)
            updated_image = image == expected_image

            time_frame = get_ima_time_frame(self.name, after=after)
            container_time_frame = get_ima_container_time_frame(self.name, self.dutils)

            updated_time_frame = time_frame == container_time_frame
            logger.debug(
                'IMA image %s, container image %s, time frame %d, container_time_frame %d',
                expected_image,
                image,
                time_frame,
                container_time_frame,
            )

        data = {
            'container_running': container_running,
            'updated_image': updated_image,
            'new_image_pulled': new_image_pulled,
            'updated_time_frame': updated_time_frame,
        }
        logger.debug('%s, IMA check - %s', self.name, data)
        result: bool = all(data.values())
        return CheckRes(result, data=data)


class SChainChecks(IChecks):
    def __init__(
        self,
        schain_name: SchainName,
        node_id: int,
        schain_record: SChainRecord,
        rule_controller: IRuleController,
        stream_version: str,
        estate: ExternalState,
        current_nodes: list[ExtendedManagerNodeInfo],
        last_dkg_successful: bool,
        rotation_id: int = 0,
        *,
        econfig: Optional[ExternalConfig] = None,
        dutils: DockerUtils | None = None,
        sync_node: bool = False,
    ):
        self._subjects = [
            ConfigChecks(
                schain_name=schain_name,
                node_id=node_id,
                schain_record=schain_record,
                rotation_id=rotation_id,
                stream_version=stream_version,
                current_nodes=current_nodes,
                last_dkg_successful=last_dkg_successful,
                estate=estate,
                econfig=econfig,
                sync_node=sync_node,
            ),
            SkaledChecks(
                schain_name=schain_name,
                schain_record=schain_record,
                rule_controller=rule_controller,
                econfig=econfig,
                dutils=dutils,
                sync_node=sync_node,
            ),
        ]

    def __getattr__(self, attr: str) -> Any:
        for subj in self._subjects:
            if attr in dir(subj):
                return getattr(subj, attr)
        raise AttributeError(f'No such attribute {attr}')

    def get_name(self) -> str:
        return self.name

    def get_all(
        self, log: bool = True, save: bool = False, needed: Optional[List[str]] = None
    ) -> dict:
        needed = needed or API_ALLOWED_CHECKS

        plain_checks = {}
        for subj in self._subjects:
            logger.debug('Running checks for %s', subj)
            subj_checks = subj.get_all(log=False, save=False, needed=needed)
            plain_checks.update(subj_checks)
        if not self.estate or not self.estate.ima_linked:
            if 'ima_container' in plain_checks:
                del plain_checks['ima_container']

        if log:
            log_checks_dict(self.get_name(), plain_checks)
        if save:
            save_checks_dict(self.get_name(), plain_checks)
        return plain_checks
