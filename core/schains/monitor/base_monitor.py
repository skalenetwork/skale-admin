#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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

import time
import logging
from datetime import datetime
from abc import ABC, abstractmethod

from skale import Skale, SkaleIma

from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.dkg import safe_run_dkg, DkgError
from core.schains.cleaner import (
    remove_config_dir,
    remove_schain_container,
    remove_schain_volume
)
from core.schains.volume import init_data_volume
from core.schains.firewall import add_firewall_rules
from core.schains.monitor.containers import monitor_schain_container, monitor_ima_container
from core.schains.monitor.rpc import monitor_schain_rpc

from core.schains.config.dir import init_schain_config_dir
from core.schains.config.generator import init_schain_config

from tools.configs.ima import DISABLE_IMA
from tools.docker_utils import DockerUtils
from tools.notifications.messages import notify_checks, is_checks_passed
from web.models.schain import upsert_schain_record


logger = logging.getLogger(__name__)


CONTAINERS_DELAY = 20
SCHAIN_MONITOR_SLEEP_INTERVAL = 500
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseMonitor(ABC):
    def __init__(
        self,
        skale: Skale,
        skale_ima: SkaleIma,
        schain: dict,
        node_config: NodeConfig,
        rotation_id: int,
        checks: SChainChecks,
        dutils: DockerUtils = None
    ):
        self.skale = skale
        self.skale_ima = skale_ima
        self.schain = schain
        self.name = schain['name']
        self.node_config = node_config
        self.checks = checks
        self.rotation_id = rotation_id
        self.dutils = dutils or DockerUtils()

        self.schain_record = upsert_schain_record(self.name)
        self.p = f'{type(self).__name__} - schain: {self.name} -'

    def _upd_last_seen(self) -> None:
        schain_record = upsert_schain_record(self.name)
        schain_record.set_monitor_last_seen(datetime.now())

    def _upd_schain_record(self) -> None:
        schain_record = upsert_schain_record(self.name)
        if schain_record.first_run:
            schain_record.set_restart_count(0)
            schain_record.set_failed_rpc_count(0)
        schain_record.set_first_run(False)
        schain_record.set_new_schain(False)
        logger.info(
            f'sChain {self.name}: '
            f'restart_count - {schain_record.restart_count}, '
            f'failed_rpc_count - {schain_record.failed_rpc_count}'
        )

    def _run_all_checks(self) -> None:
        checks_dict = self.checks.get_all()
        if not is_checks_passed(checks_dict):
            notify_checks(self.name, self.node_config.all(), checks_dict)

    def _monitor_runner(func):
        def monitor_runner(self):
            logger.info(f'{self.p} starting monitor runner')
            self._upd_last_seen()
            try:
                schain_record = upsert_schain_record(self.name)
                if not schain_record.first_run:
                    self._run_all_checks()
                self._upd_schain_record()
                res = func(self)
                self._upd_last_seen()
                logger.info(f'{self.p} finished monitor runner')
                return res
            except Exception as e:
                print(f'{self.p} monitor runner failed')
                logger.exception(e)
        return monitor_runner

    @abstractmethod
    def run(self):
        pass

    def config_dir(self) -> None:
        if not self.checks.config_dir.status:
            init_schain_config_dir(self.name)
        else:
            logger.info(f'{self.p} config_dir - ok')

    def dkg(self) -> None:
        if not self.checks.dkg.status:
            is_dkg_done = safe_run_dkg(
                skale=self.skale,
                schain_name=self.name,
                node_id=self.node_config.id,
                sgx_key_name=self.node_config.sgx_key_name,
                rotation_id=self.rotation_id,
                schain_record=self.schain_record
            )
            if not is_dkg_done:
                remove_config_dir(self.name)
                raise DkgError(f'{self.p} DKG failed')
        else:
            logger.info(f'{self.p} dkg - ok')

    def config(self) -> None:
        if not self.checks.config.status:
            init_schain_config(
                skale=self.skale,
                node_id=self.node_config.id,
                schain_name=self.name,
                ecdsa_sgx_key_name=self.node_config.sgx_key_name,
                rotation_id=self.rotation_id,
                schain_record=self.schain_record
            )
        else:
            logger.info(f'{self.p} config - ok')

    def volume(self) -> None:
        if not self.checks.volume.status:
            init_data_volume(self.schain, dutils=self.dutils)
        else:
            logger.info(f'{self.p} volume - ok')

    def firewall_rules(self) -> None:
        if not self.checks.firewall_rules.status:
            add_firewall_rules(self.name)
        else:
            logger.info(f'{self.p} firewall_rules - ok')

    def skaled_container(self, sync: bool) -> None:  # todo: handle sync!
        skaled_container_check = self.checks.skaled_container
        if not skaled_container_check.status:
            monitor_schain_container(
                self.schain,
                schain_record=self.schain_record,
                dutils=self.dutils
            )
            time.sleep(CONTAINERS_DELAY)
        else:
            self.schain_record.set_restart_count(0)
            logger.info(f'{self.p} skaled_container - ok')

    def skaled_rpc(self) -> None:
        if not self.checks.rpc.status:
            monitor_schain_rpc(
                self.schain,
                schain_record=self.schain_record,
                dutils=self.dutils
            )
        else:
            self.schain_record.set_failed_rpc_count(0)
            logger.info(f'{self.p} rpc - ok')

    def ima_container(self) -> None:
        if not DISABLE_IMA and not self.checks.ima_container:
            monitor_ima_container(self.skale_ima, self.schain, dutils=self.dutils)
        else:
            logger.info(f'{self.p} ima_container - ok')

    def cleanup_schain_docker_entity(self) -> None:
        remove_schain_container(self.name, dutils=self.dutils)
        time.sleep(SCHAIN_CLEANUP_TIMEOUT)
        remove_schain_volume(self.name, dutils=self.dutils)

    _monitor_runner = staticmethod(_monitor_runner)
