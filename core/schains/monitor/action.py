#   -*- coding: utf-8 -*-
#
#  This file is part of SKALE Admin
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
from typing import Optional

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
from core.schains.rotation import set_rotation_for_schain

from core.schains.limits import get_schain_type

from core.schains.monitor.containers import monitor_schain_container, monitor_ima_container
from core.schains.monitor.rpc import handle_failed_schain_rpc
from core.schains.runner import (
    restart_container,
    is_container_exists,
    get_container_name
)
from core.schains.config.main import (
    create_new_schain_config,
    get_finish_ts_from_config,
    get_finish_ts_from_upstream_config,
    get_upstream_config_filepath,
    sync_config_with_file
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

from tools.notifications.messages import notify_repair_mode
from web.models.schain import (
    SChainRecord,
    set_first_run,
    switch_off_repair_mode,
    upsert_schain_record
)


logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseActionManager:
    def __init__(self, name: str):
        self.name = name
        self.executed_blocks = {}

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
            f'restart_count - {self.schain_record.restart_count}, '
            f'failed_rpc_count - {self.schain_record.failed_rpc_count}'
        )

    def log_executed_blocks(self) -> None:
        logger.info(arguments_list_string(
            self.executed_blocks, f'Finished monitor runner - {self.name}'))


class ConfigActionManager(BaseActionManager):
    def __init__(
        self,
        skale: Skale,
        schain: dict,
        node_config: NodeConfig,
        rotation_data: dict,
        stream_version: str,
        checks: IChecks
    ):
        self.skale = skale
        self.schain = schain
        self.generation = schain['generation']
        self.node_config = node_config
        self.checks = checks
        self.stream_version = stream_version

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data['rotation_id']
        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def config_dir(self) -> bool:
        initial_status = self.checks.config_dir.status
        if not initial_status:
            init_schain_config_dir(self.name)
        else:
            logger.info('config_dir - ok')
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
                raise DkgError('DKG failed')
        else:
            logger.info('dkg - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def upstream_config(self) -> bool:
        initial_status = self.checks.upstream_config
        if not initial_status:
            create_new_schain_config(
                skale=self.skale,
                node_id=self.node_config.id,
                schain_name=self.name,
                generation=self.generation,
                ecdsa_sgx_key_name=self.node_config.sgx_key_name,
                rotation_data=self.rotation_data,
                stream_version=self.stream_version,
                schain_record=self.schain_record
            )
        else:
            logger.info('config - ok')
        return initial_status


class SkaledActionManager(BaseActionManager):
    def __init__(
        self,
        schain: dict,
        ima_data: ImaData,
        rule_controller: IRuleController,
        public_key: str,
        checks: IChecks,
        node_config: NodeConfig,
        dutils: DockerUtils = None
    ):
        self.ima_data = ima_data
        self.schain = schain
        self.generation = schain['generation']
        self.checks = checks
        self.node_config = node_config

        self.rc = rule_controller
        self.skaled_status = init_skaled_status(self.schain['name'])
        self.schain_type = get_schain_type(schain['partOfNode'])
        self.public_key = public_key

        self.dutils = dutils or DockerUtils()

        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            init_data_volume(self.schain, dutils=self.dutils)
        else:
            logger.info('Volume - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def firewall_rules(self, overwrite=False) -> bool:
        initial_status = self.checks.firewall_rules
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
    def skaled_container(
        self,
        download_snapshot: bool = False,
        start_ts: Optional[int] = None
    ) -> bool:
        initial_status = self.checks.skaled_container.status
        if not initial_status:
            public_key = None
            if download_snapshot:
                public_key = self.public_key

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
            logger.info('skaled_container - ok')
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
        logger.info('starting skaled with reloaded configuration')
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            remove_schain_container(self.name, dutils=self.dutils)
        else:
            logger.warning('container doesn\'t exists')
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
            logger.info('rpc - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container
        if not initial_status:
            logger.info('trying to run IMA container')
            monitor_ima_container(
                self.schain,
                self.ima_data,
                dutils=self.dutils
            )
        else:
            logger.info('ima_container - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def cleanup_schain_docker_entity(self) -> bool:
        logger.info('removing docker artifacts')
        remove_schain_container(self.name, dutils=self.dutils)
        time.sleep(SCHAIN_CLEANUP_TIMEOUT)
        remove_schain_volume(self.name, dutils=self.dutils)
        return True

    @BaseActionManager.monitor_block
    def update_config(self) -> bool:
        upstream_path = get_upstream_config_filepath(self.name)
        if upstream_path:
            logger.info('syncing with upstream %s', upstream_path)
            sync_config_with_file(self.name, upstream_path)
        logger.info('no upstream config yet')
        return upstream_path is not None

    @BaseActionManager.monitor_block
    def send_exit_request(self) -> None:
        finish_ts = self.upstream_finish_ts
        if finish_ts is not None:
            set_rotation_for_schain(self.name, finish_ts)

    @property
    def upstream_config_path(self) -> Optional[str]:
        return get_upstream_config_filepath(self.name)

    @property
    def upstream_finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_upstream_config(self.name)

    @property
    def finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_config(self.name)

    def display_skaled_logs(self) -> None:
        if is_container_exists(self.name, dutils=self.dutils):
            container_name = get_container_name(SCHAIN_CONTAINER, self.name)
            self.dutils.display_container_logs(container_name)
        else:
            logger.warning(f'sChain {self.name}: container doesn\'t exists, could not show logs')

    @BaseActionManager.monitor_block
    def notify_repair_mode(self) -> None:
        notify_repair_mode(
            self.node_config.all(),
            self.name
        )

    @BaseActionManager.monitor_block
    def disable_repair_mode(self) -> None:
        switch_off_repair_mode(self.name)
