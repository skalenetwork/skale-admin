#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021-Present SKALE Labs
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
from enum import Enum
from functools import wraps

from skale import Skale
from skale.schain_config.generator import get_nodes_for_schain

from core.node_config import NodeConfig
from core.schains.checks import ConfigCheckMsg, SChainChecks
from core.schains.dkg import safe_run_dkg, save_dkg_results, DkgError
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.firewall.types import IRuleController
from core.schains.cleaner import (
    remove_schain_container,
    remove_schain_volume
)
from core.schains.config.main import save_schain_config, update_schain_config_version
from core.schains.config.generator import generate_schain_config_with_skale

from core.schains.volume import init_data_volume
from core.schains.rotation import get_schain_public_key

from core.schains.limits import get_schain_type

from core.schains.monitor.containers import (
    monitor_ima_container,
    monitor_schain_container,
    schedule_exit
)
from core.schains.monitor.rpc import handle_failed_schain_rpc
from core.schains.runner import (
    restart_container, is_container_exists, get_container_name
)
from core.schains.config import init_schain_config_dir
from core.schains.config.directory import get_schain_config
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config
)
from core.schains.ima import ImaData
from core.schains.skaled_status import init_skaled_status

from tools.docker_utils import DockerUtils
from tools.notifications.messages import notify_checks, is_checks_passed
from tools.str_formatters import arguments_list_string
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import upsert_schain_record, set_first_run, SChainRecord


logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class ConfigStatus(int, Enum):
    OK = 0
    SAVED = 1
    RELOAD_NEEDED = 2


class BaseMonitor(ABC):
    def __init__(
        self,
        skale: Skale,
        ima_data: ImaData,
        schain: dict,
        node_config: NodeConfig,
        rotation_data: dict,
        checks: SChainChecks,
        rule_controller: IRuleController,
        dutils: DockerUtils = None
    ):
        self.skale = skale
        self.ima_data = ima_data
        self.schain = schain
        self.name = schain['name']
        self.generation = schain['generation']
        self.node_config = node_config
        self.checks = checks
        self.executed_blocks = {}

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data['rotation_id']
        self.rc = rule_controller

        self.finish_ts = skale.node_rotation.get_schain_finish_ts(
            node_id=rotation_data['leaving_node'],
            schain_name=self.name
        )
        logger.info(f'sChain finish_ts calculated: {self.finish_ts}')

        self.skaled_status = init_skaled_status(self.name)

        self.schain_type = get_schain_type(schain['partOfNode'])

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

    def _run_all_checks(self, save_checks=True) -> None:
        checks_dict = self.checks.get_all(save=save_checks)
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
            logger.info('%s finished monitor runner', self.p)
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
            logger.info('%s config_dir - ok', self.p)
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
            logger.info('%s dkg - ok', self.p)
        return initial_status

    @monitor_block
    def config(self, overwrite=False) -> ConfigStatus:
        schain_config = generate_schain_config_with_skale(
            skale=self.skale,
            schain_name=self.name,
            generation=self.generation,
            node_id=self.node_config.id,
            rotation_data=self.rotation_data,
            ecdsa_key_name=self.node_config.sgx_key_name
        )
        self.checks.needed_config = schain_config.to_dict()
        check_result = self.checks.config
        logger.info('%s config check result %s', self.p, check_result.msg)
        if overwrite or check_result.msg == ConfigCheckMsg.NO_FILE:
            logger.info('%s updating config', self.p)
            save_schain_config(schain_config.to_dict(), self.name)
            update_schain_config_version(self.name, schain_record=self.schain_record)
        elif not check_result.status:
            logger.info('%s config is outdated', self.p)
            return ConfigStatus.RELOAD_NEEDED
        else:
            logger.info('%s config - ok', self.p)
            return ConfigStatus.OK

    @monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            init_data_volume(self.schain, dutils=self.dutils)
        else:
            logger.info('%s volume - ok', self.p)
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
            self.rc.configure(
                base_port=base_port,
                own_ip=own_ip,
                node_ips=node_ips
            )
            self.rc.sync()
        return initial_status

    def schedule_skaled_exit(self):
        if not self.schain_record.exit_requested:
            logger.info('%s requesting exit', self.p)
            schain_nodes = get_nodes_for_schain(self.skale, self.name)
            schedule_exit(self.name, schain_nodes, self.node_config.id)
            self.schain_record.exit_requested(True)
        else:
            logger.info('%s exit has been already requested', self.p)

    @monitor_block
    def skaled_container(self, download_snapshot: bool = False, delay_start: bool = False) -> bool:
        initial_status = self.checks.skaled_container.status
        if not initial_status:
            public_key, start_ts = None, None

            if download_snapshot:
                public_key = get_schain_public_key(self.skale, self.name)
            if delay_start:
                start_ts = self.finish_ts

            monitor_schain_container(
                self.schain,
                schain_record=self.schain_record,
                skaled_status=self.skaled_status,
                public_key=public_key,
                start_ts=start_ts,
                dutils=self.dutils
            )
            time.sleep(CONTAINER_POST_RUN_DELAY)
        else:
            self.schain_record.set_restart_count(0)
            logger.info('%s skaled_container - ok', self.p)
        return initial_status

    @monitor_block
    def restart_skaled_container(self) -> bool:
        initial_status = True
        if not is_container_exists(self.name, dutils=self.dutils):
            logger.info('%s: container doesn\'t exits, running container...', self.p)
            initial_status = self.skaled_container()
        else:
            restart_container(SCHAIN_CONTAINER, self.schain, dutils=self.dutils)
        return initial_status

    @monitor_block
    def reloaded_skaled_container(self) -> bool:
        logger.info('Starting skaled with reloaded configuration')
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            remove_schain_container(self.name, dutils=self.dutils)
        else:
            logger.warning('%s: container doesn\'t exists', self.p)
        initial_status = self.skaled_container()
        return initial_status

    @monitor_block
    def skaled_rpc(self) -> bool:
        initial_status = self.checks.rpc.status
        if not initial_status:
            self.display_skaled_logs()
            handle_failed_schain_rpc(
                self.schain,
                schain_record=self.schain_record,
                skaled_status=self.skaled_status,
                dutils=self.dutils
            )
        else:
            self.schain_record.set_failed_rpc_count(0)
            logger.info('%s rpc - ok', self.p)
        return initial_status

    @monitor_block
    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container.status
        if not initial_status:
            monitor_ima_container(
                self.schain,
                self.ima_data,
                dutils=self.dutils
            )
        else:
            logger.info('%s ima_container - ok', self.p)
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

    def display_skaled_logs(self) -> None:
        if is_container_exists(self.name, dutils=self.dutils):
            container_name = get_container_name(SCHAIN_CONTAINER, self.name)
            self.dutils.display_container_logs(container_name)
        else:
            logger.warning('%s: container doesn\'t exists, could not show logs', self.p)

    monitor_runner = staticmethod(monitor_runner)
    monitor_block = staticmethod(monitor_block)
