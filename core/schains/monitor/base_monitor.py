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
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from typing import Callable

from skale import Skale


from core.ima.schain import copy_schain_ima_abi
from core.node_config import NodeConfig
from core.schains.checks import SChainChecks
from core.schains.dkg import safe_run_dkg, save_dkg_results, DkgError
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.cleaner import (
    remove_schain_container,
    remove_schain_volume
)
from core.schains.runner import run_ima_container

from core.schains.volume import init_data_volume
from core.schains.rotation import get_schain_public_key

from core.schains.monitor.containers import monitor_schain_container
from core.schains.monitor.rpc import monitor_schain_rpc

from core.schains.config.directory import (
    get_schain_config,
    init_schain_config_dir
)
from core.schains.config.generator import init_schain_config
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config
)
from core.schains.ima import ImaData

from tools.configs.ima import DISABLE_IMA
from tools.docker_utils import DockerUtils
from tools.notifications.messages import notify_checks, is_checks_passed
from tools.str_formatters import arguments_list_string

from web.models.schain import upsert_schain_record, set_first_run, SChainRecord


logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseMonitor(ABC):
    def __init__(
        self,
        skale: Skale,
        ima_data: ImaData,
        schain: dict,
        node_config: NodeConfig,
        rotation_data: dict,
        checks: SChainChecks,
        rule_controller_creator: Callable,
        dutils: DockerUtils = None
    ):
        self.skale = skale
        self.ima_data = ima_data
        self.schain = schain
        self.name = schain['name']
        self.node_config = node_config
        self.checks = checks
        self.executed_blocks = {}

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data['rotation_id']
        self.rc_creator = rule_controller_creator

        self.dutils = dutils or DockerUtils()
        self.p = f'{type(self).__name__} - schain: {self.name} -'

    @property
    def schain_record(self):
        return upsert_schain_record(self.name)

    def _upd_last_seen(self) -> None:
        self.schain_record.set_monitor_last_seen(datetime.now())

    def _upd_schain_record(self) -> None:
        if self.schain_record.first_run:
            self.schain_record.set_restart_count(0)
            self.schain_record.set_failed_rpc_count(0)
        set_first_run(self.name, False)
        self.schain_record.set_new_schain(False)
        logger.info(
            f'sChain {self.name}: '
            f'restart_count - {self.schain_record.restart_count}, '
            f'failed_rpc_count - {self.schain_record.failed_rpc_count}'
        )

    def _run_all_checks(self) -> None:
        checks_dict = self.checks.get_all()
        if not is_checks_passed(checks_dict):
            notify_checks(self.name, self.node_config.all(), checks_dict)

    def monitor_block(f):
        @wraps(f)
        def _monitor_block(self, *args, **kwargs):
            ts = time.time()
            initial_status = f(self, *args, **kwargs)
            te = time.time()
            self.executed_blocks[f.__name__] = {
                'ts': ts,
                'te': te,
                'initial_status': initial_status
            }
            return initial_status
        return _monitor_block

    def monitor_runner(f):
        @wraps(f)
        def _monitor_runner(self):
            logger.info(arguments_list_string({
                'Monitor type': type(self).__name__,
                'Rotation data': self.rotation_data,
                'sChain record': SChainRecord.to_dict(self.schain_record)
            }, f'Starting monitor runner - {self.name}'))

            self._upd_last_seen()
            if not self.schain_record.first_run:
                self._run_all_checks()
            self._upd_schain_record()
            res = f(self)
            self._upd_last_seen()
            self.log_executed_blocks()
            logger.info(f'{self.p} finished monitor runner')
            return res
        return _monitor_runner

    @abstractmethod
    def run(self):
        pass

    @monitor_block
    def config_dir(self) -> bool:
        initial_status = self.checks.config_dir.status
        if not initial_status:
            init_schain_config_dir(self.name)
        else:
            logger.info(f'{self.p} config_dir - ok')
        return initial_status

    @monitor_block
    def dkg(self) -> bool:
        initial_status = self.checks.dkg.status
        if not initial_status:
            dkg_result = safe_run_dkg(
                skale=self.skale,
                schain_name=self.name,
                node_id=self.node_config.id,
                sgx_key_name=self.node_config.sgx_key_name,
                rotation_id=self.rotation_id
            )
            if dkg_result.status.is_done():
                save_dkg_results(
                    dkg_result.keys_data,
                    get_secret_key_share_filepath(self.name, self.rotation_id)
                )
            self.schain_record.set_dkg_status(dkg_result.status)
            if not dkg_result.status.is_done():
                raise DkgError(f'{self.p} DKG failed')
        else:
            logger.info(f'{self.p} dkg - ok')
        return initial_status

    @monitor_block
    def config(self, overwrite=False) -> bool:
        initial_status = self.checks.config.status
        if not initial_status or overwrite:
            init_schain_config(
                skale=self.skale,
                node_id=self.node_config.id,
                schain_name=self.name,
                ecdsa_sgx_key_name=self.node_config.sgx_key_name,
                rotation_data=self.rotation_data,
                schain_record=self.schain_record
            )
        else:
            logger.info(f'{self.p} config - ok')
        return initial_status

    @monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            init_data_volume(self.schain, dutils=self.dutils)
        else:
            logger.info(f'{self.p} volume - ok')
        return initial_status

    @monitor_block
    def firewall_rules(self, overwrite=False) -> bool:
        initial_status = self.checks.firewall_rules.status
        if not initial_status:
            logger.info('Configuring firewall rules')
            conf = get_schain_config(self.name)
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)
            rc = self.rc_creator(self.name, base_port, own_ip, node_ips)
            rc.sync()
        return initial_status

    @monitor_block
    def skaled_container(self, sync: bool = False) -> bool:
        initial_status = self.checks.skaled_container.status
        if not initial_status:

            if sync:
                public_key = get_schain_public_key(self.skale, self.name)
                start_ts = self.rotation_data['finish_ts']
            else:
                public_key, start_ts = None, None

            monitor_schain_container(
                self.schain,
                schain_record=self.schain_record,
                public_key=public_key,
                start_ts=start_ts,
                dutils=self.dutils
            )
            time.sleep(CONTAINER_POST_RUN_DELAY)
        else:
            self.schain_record.set_restart_count(0)
            logger.info(f'{self.p} skaled_container - ok')
        return initial_status

    @monitor_block
    def skaled_rpc(self) -> bool:
        initial_status = self.checks.rpc.status
        if not initial_status:
            monitor_schain_rpc(
                self.schain,
                schain_record=self.schain_record,
                dutils=self.dutils
            )
        else:
            self.schain_record.set_failed_rpc_count(0)
            logger.info(f'{self.p} rpc - ok')
        return initial_status

    @monitor_block
    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container.status
        if not DISABLE_IMA and not initial_status:
            if self.ima_data.linked:
                copy_schain_ima_abi(self.name)
                run_ima_container(
                    self.schain,
                    self.ima_data.chain_id,
                    dutils=self.dutils
                )
            else:
                logger.warning(f'{self.p} not registered in IMA')
        else:
            logger.info(f'{self.p} ima_container - ok')
        return initial_status

    @monitor_block
    def cleanup_schain_docker_entity(self) -> bool:
        remove_schain_container(self.name, dutils=self.dutils)
        time.sleep(SCHAIN_CLEANUP_TIMEOUT)
        remove_schain_volume(self.name, dutils=self.dutils)
        return True

    def log_executed_blocks(self) -> None:
        logger.info(arguments_list_string(
            self.executed_blocks, f'Finished monitor runner - {self.name}'))

    monitor_runner = staticmethod(monitor_runner)
    monitor_block = staticmethod(monitor_block)
