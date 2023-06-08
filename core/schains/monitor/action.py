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
from datetime import datetime
from functools import wraps

from skale import Skale

from core.node_config import NodeConfig
from core.schains.checks import IChecks
from core.schains.dkg import safe_run_dkg, save_dkg_results, DkgError
from core.schains.dkg.utils import get_secret_key_share_filepath
from core.schains.cleaner import (
    remove_schain_container,
    remove_schain_volume
)
from core.schains.firewall.types import IRuleController

from core.schains.volume import init_data_volume
from core.schains.rotation import (
    get_schain_public_key,
    set_rotation_for_schain
)

from core.schains.limits import get_schain_type

from core.schains.monitor.containers import monitor_schain_container, monitor_ima_container
from core.schains.monitor.rpc import handle_failed_schain_rpc
from core.schains.runner import (
    restart_container,
    is_container_exists,
    get_container_name
)
from core.schains.config.main import (
    get_latest_config_filepath,
    init_schain_config2,
    set_as_upstream_config
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
from tools.str_formatters import arguments_list_string
from tools.configs.containers import SCHAIN_CONTAINER

from web.models.schain import upsert_schain_record, set_first_run, SChainRecord


logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseActionManager:
    def __init__(self, name: str):
        self.name = name
        self.executed_blocks = {}
        self.p = f'{type(self).__name__} - schain: {self.name} -'

    @staticmethod
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

    @property
    def schain_record(self) -> SChainRecord:
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


class ConfigActionManager(BaseActionManager):
    def __init__(
        self,
        skale: Skale,
        schain: dict,
        node_config: NodeConfig,
        rotation_data: dict,
        checks: IChecks
    ):
        self.skale = skale
        self.schain = schain
        self.generation = schain['generation']
        self.node_config = node_config
        self.checks = checks

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data['rotation_id']
        self.finish_ts = skale.node_rotation.get_schain_finish_ts(
            node_id=rotation_data['leaving_node'],
            schain_name=self.schain['name']
        )
        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def config_dir(self) -> bool:
        initial_status = self.checks.config_dir.status
        if not initial_status:
            init_schain_config_dir(self.name)
        else:
            logger.info(f'{self.p} config_dir - ok')
        return initial_status

    @BaseActionManager.monitor_block
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

    @BaseActionManager.monitor_block
    def config(self, overwrite=False) -> bool:
        initial_status = self.checks.config.status
        if not initial_status or overwrite:
            init_schain_config2(
                skale=self.skale,
                node_id=self.node_config.id,
                schain_name=self.name,
                generation=self.generation,
                ecdsa_sgx_key_name=self.node_config.sgx_key_name,
                rotation_data=self.rotation_data,
                schain_record=self.schain_record
            )
        else:
            logger.info(f'{self.p} config - ok')
        return initial_status


class SkaledActionManager(BaseActionManager):
    def __init__(
        self,
        schain: dict,
        ima_data: ImaData,
        rule_controller: IRuleController,
        finish_ts: int,
        checks: IChecks,
        dutils: DockerUtils = None
    ):
        self.ima_data = ima_data
        self.schain = schain
        self.generation = schain['generation']
        self.checks = checks

        self.rc = rule_controller
        self.skaled_status = init_skaled_status(self.schain['name'])
        self.schain_type = get_schain_type(schain['partOfNode'])

        self.dutils = dutils or DockerUtils()

        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            init_data_volume(self.schain, dutils=self.dutils)
        else:
            logger.info(f'{self.p} volume - ok')
        return initial_status

    @BaseActionManager.monitor_block
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

    @BaseActionManager.monitor_block
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
            logger.info(f'{self.p} skaled_container - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def restart_skaled_container(self) -> bool:
        initial_status = True
        if not is_container_exists(self.name, dutils=self.dutils):
            logger.info(f'sChain {self.name}: container doesn\'t exits, running container...')
            initial_status = self.skaled_container()
        else:
            restart_container(SCHAIN_CONTAINER, self.schain, dutils=self.dutils)
        return initial_status

    @BaseActionManager.monitor_block
    def reloaded_skaled_container(self) -> bool:
        logger.info('Starting skaled with reloaded configuration')
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            remove_schain_container(self.name, dutils=self.dutils)
        else:
            logger.warning(f'sChain {self.name}: container doesn\'t exists')
        self.schain_record.set_restart_count(0)
        self.schain_record.set_failed_rpc_count(0)
        self.schain_record.set_needs_reload(False)
        initial_status = self.skaled_container()
        return initial_status

    @BaseActionManager.monitor_block
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
            logger.info(f'{self.p} rpc - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container.status
        if not initial_status:
            monitor_ima_container(
                self.schain,
                self.ima_data,
                dutils=self.dutils
            )
        else:
            logger.info(f'{self.p} ima_container - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def cleanup_schain_docker_entity(self) -> bool:
        remove_schain_container(self.name, dutils=self.dutils)
        time.sleep(SCHAIN_CLEANUP_TIMEOUT)
        remove_schain_volume(self.name, dutils=self.dutils)
        return True

    @BaseActionManager.monitor_block
    def fetch_upstream_config(self) -> bool:
        latest_filepath = get_latest_config_filepath(self.name)
        set_as_upstream_config(self.name, latest_filepath)

    def send_exit_request(self) -> None:
        set_rotation_for_schain(self.name, self.finish_ts)

    def log_executed_blocks(self) -> None:
        logger.info(arguments_list_string(
            self.executed_blocks, f'Finished monitor runner - {self.name}'))

    def display_skaled_logs(self) -> None:
        if is_container_exists(self.name, dutils=self.dutils):
            container_name = get_container_name(SCHAIN_CONTAINER, self.name)
            self.dutils.display_container_logs(container_name)
        else:
            logger.warning(f'sChain {self.name}: container doesn\'t exists, could not show logs')
