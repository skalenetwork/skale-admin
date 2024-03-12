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

import logging
import time
from datetime import datetime
from functools import wraps
from typing import Dict, Optional, List

from skale import Skale

from core.node_config import NodeConfig
from core.node import ExtendedManagerNodeInfo, calc_reload_ts, get_node_index_in_group
from core.schains.checks import ConfigChecks, SkaledChecks
from core.schains.dkg import (
    DkgError,
    get_dkg_client,
    get_secret_key_share_filepath,
    run_dkg,
    save_dkg_results
)
from core.schains.ima import get_migration_ts as get_ima_migration_ts
from core.schains.ssl import update_ssl_change_date

from core.schains.cleaner import (
    remove_ima_container,
    remove_schain_container,
    remove_schain_volume
)
from core.schains.firewall.types import IRuleController

from core.schains.volume import init_data_volume
from core.schains.exit_scheduler import ExitScheduleFileManager

from core.schains.limits import get_schain_type

from core.schains.monitor.containers import monitor_schain_container, monitor_ima_container
from core.schains.monitor.rpc import handle_failed_schain_rpc
from core.schains.runner import (
    get_container_name,
    is_container_exists,
    pull_new_image,
    restart_container
)
from core.schains.config.main import (
    create_new_upstream_config,
    get_finish_ts_from_skaled_config,
    get_finish_ts_from_latest_upstream
)
from core.schains.config import init_schain_config_dir
from core.schains.config.main import update_schain_config_version
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.helper import (
    get_base_port_from_config,
    get_node_ips_from_config,
    get_own_ip_from_config
)
from core.schains.ima import ImaData
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.skaled_status import init_skaled_status

from tools.docker_utils import DockerUtils
from tools.node_options import NodeOptions
from tools.str_formatters import arguments_list_string
from tools.configs import SYNC_NODE
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER

from tools.notifications.messages import notify_repair_mode
from web.models.schain import SChainRecord, upsert_schain_record


logger = logging.getLogger(__name__)


CONTAINER_POST_RUN_DELAY = 20
SCHAIN_CLEANUP_TIMEOUT = 10


class BaseActionManager:
    def __init__(self, name: str):
        self.name = name
        self.executed_blocks: Dict = {}

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
        self.schain_record.set_first_run(False)
        self.schain_record.set_new_schain(False)
        logger.info(
            'restart_count - %s, failed_rpc_count - %s',
            self.schain_record.restart_count,
            self.schain_record.failed_rpc_count
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
        checks: ConfigChecks,
        estate: ExternalState,
        current_nodes: List[ExtendedManagerNodeInfo],
        econfig: Optional[ExternalConfig] = None,
        node_options: NodeOptions = None
    ):
        self.skale = skale
        self.schain = schain
        self.generation = schain['generation']
        self.node_config = node_config
        self.checks = checks
        self.stream_version = stream_version
        self.current_nodes = current_nodes

        self.rotation_data = rotation_data
        self.rotation_id = rotation_data['rotation_id']
        self.estate = estate
        self.econfig = econfig or ExternalConfig(name=schain['name'])
        self.node_options = node_options or NodeOptions()
        self.cfm: ConfigFileManager = ConfigFileManager(
            schain_name=self.schain['name']
        )
        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def config_dir(self) -> bool:
        logger.info('Initializing config dir')
        init_schain_config_dir(self.name)
        return True

    @BaseActionManager.monitor_block
    def dkg(self) -> bool:
        initial_status = self.checks.dkg.status
        if not initial_status:
            logger.info('Initing dkg client')
            dkg_client = get_dkg_client(
                skale=self.skale,
                node_id=self.node_config.id,
                schain_name=self.name,
                sgx_key_name=self.node_config.sgx_key_name,
                rotation_id=self.rotation_id
            )
            logger.info('Running run_dkg')
            dkg_result = run_dkg(
                dkg_client=dkg_client,
                skale=self.skale,
                schain_name=self.name,
                node_id=self.node_config.id,
                sgx_key_name=self.node_config.sgx_key_name,
                rotation_id=self.rotation_id
            )
            logger.info('DKG finished with %s', dkg_result)
            if dkg_result.status.is_done():
                save_dkg_results(
                    dkg_result.keys_data,
                    get_secret_key_share_filepath(self.name, self.rotation_id)
                )
            self.schain_record.set_dkg_status(dkg_result.status)
            if not dkg_result.status.is_done():
                raise DkgError('DKG failed')
        else:
            logger.info('Dkg - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def upstream_config(self) -> bool:
        logger.info(
            'Creating new upstream_config rotation_id: %s, stream: %s',
            self.rotation_data.get('rotation_id'), self.stream_version
        )
        new_config = create_new_upstream_config(
            skale=self.skale,
            node_id=self.node_config.id,
            schain_name=self.name,
            generation=self.generation,
            ecdsa_sgx_key_name=self.node_config.sgx_key_name,
            rotation_data=self.rotation_data,
            sync_node=SYNC_NODE,
            node_options=self.node_options
        )

        result = False
        if not self.cfm.upstream_config_exists() or new_config != self.cfm.latest_upstream_config:
            rotation_id = self.rotation_data['rotation_id']
            logger.info(
                'Saving new upstream config rotation_id: %d, ips: %s',
                rotation_id,
                self.current_nodes
            )
            self.cfm.save_new_upstream(rotation_id, new_config)
            result = True
        else:
            logger.info('Generated config is the same as latest upstream')

        update_schain_config_version(
            self.name, schain_record=self.schain_record)
        return result

    @BaseActionManager.monitor_block
    def reset_config_record(self) -> bool:
        update_schain_config_version(
            self.name, schain_record=self.schain_record)
        self.schain_record.set_sync_config_run(False)
        return True

    @BaseActionManager.monitor_block
    def external_state(self) -> bool:
        logger.info('Updating external state config')
        logger.debug('New state %s', self.estate)
        self.econfig.update(self.estate)
        return True

    @BaseActionManager.monitor_block
    def update_reload_ts(self, ip_matched: bool, sync_node: bool = False) -> bool:
        '''
        - If ip_matched is True, then config is synced and skaled reload is not needed
        - If ip_matched is False, then config is not synced and skaled reload is needed

        For sync node node_index_in_group is always 0 to reload sync nodes immediately
        '''
        logger.info('Setting reload_ts')
        if ip_matched:
            logger.info('Resetting reload_ts')
            self.estate.reload_ts = None
            self.econfig.update(self.estate)
            return True

        node_index_in_group = 0
        if not sync_node:
            node_index_in_group = get_node_index_in_group(
                self.skale,
                self.name,
                self.node_config.id
            )
            if node_index_in_group is None:
                logger.warning(f'node {self.node_config.id} is not in chain {self.name}')
                return False
        self.estate.reload_ts = calc_reload_ts(self.current_nodes, node_index_in_group)
        logger.info(f'Setting reload_ts to {self.estate.reload_ts}')
        self.econfig.update(self.estate)
        return True


class SkaledActionManager(BaseActionManager):
    def __init__(
        self,
        schain: dict,
        rule_controller: IRuleController,
        checks: SkaledChecks,
        node_config: NodeConfig,
        econfig: Optional[ExternalConfig] = None,
        dutils: DockerUtils = None,
        node_options: NodeOptions = None
    ):
        self.schain = schain
        self.generation = schain['generation']
        self.checks = checks
        self.node_config = node_config

        self.rc = rule_controller
        self.skaled_status = init_skaled_status(self.schain['name'])
        self.schain_type = get_schain_type(schain['partOfNode'])
        self.econfig = econfig or ExternalConfig(schain['name'])
        self.cfm: ConfigFileManager = ConfigFileManager(
            schain_name=self.schain['name']
        )

        self.esfm = ExitScheduleFileManager(schain['name'])
        self.dutils = dutils or DockerUtils()

        self.node_options = node_options or NodeOptions()

        super().__init__(name=schain['name'])

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            logger.info('Creating volume')
            init_data_volume(self.schain, sync_node=SYNC_NODE, dutils=self.dutils)
        else:
            logger.info('Volume - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def firewall_rules(self, upstream: bool = False) -> bool:
        initial_status = self.checks.firewall_rules.status
        if not initial_status:
            logger.info('Configuring firewall rules')

            conf = self.cfm.latest_upstream_config if upstream else self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)

            logger.debug('Base port %d', base_port)

            ranges = self.econfig.ranges
            logger.info('Adding ranges %s', ranges)
            self.rc.configure(
                base_port=base_port,
                own_ip=own_ip,
                node_ips=node_ips,
                sync_ip_ranges=ranges
            )
            self.rc.sync()
        return initial_status

    @BaseActionManager.monitor_block
    def skaled_container(
        self,
        download_snapshot: bool = False,
        start_ts: Optional[int] = None,
        abort_on_exit: bool = True,
    ) -> bool:
        logger.info(
            'Starting skaled container watchman snapshot: %s, start_ts: %s',
            download_snapshot,
            start_ts
        )
        monitor_schain_container(
            self.schain,
            schain_record=self.schain_record,
            skaled_status=self.skaled_status,
            download_snapshot=download_snapshot,
            start_ts=start_ts,
            abort_on_exit=abort_on_exit,
            dutils=self.dutils,
            sync_node=SYNC_NODE,
            historic_state=self.node_options.historic_state
        )
        time.sleep(CONTAINER_POST_RUN_DELAY)
        return True

    @BaseActionManager.monitor_block
    def restart_skaled_container(self) -> bool:
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            logger.info('Skaled container exists, restarting')
            restart_container(SCHAIN_CONTAINER, self.schain,
                              dutils=self.dutils)
        else:
            logger.info(
                'Skaled container doesn\'t exists, running skaled watchman')
            initial_status = self.skaled_container()
        return initial_status

    @BaseActionManager.monitor_block
    def restart_ima_container(self) -> bool:
        initial_status = True
        if is_container_exists(self.name, container_type=IMA_CONTAINER, dutils=self.dutils):
            logger.info('IMA container exists, restarting')
            restart_container(IMA_CONTAINER, self.schain, dutils=self.dutils)
        else:
            logger.info(
                'IMA container doesn\'t exists, running skaled watchman')
            initial_status = self.ima_container()
        return initial_status

    @BaseActionManager.monitor_block
    def reset_restart_counter(self) -> bool:
        self.schain_record.set_restart_count(0)
        return True

    @BaseActionManager.monitor_block
    def reloaded_skaled_container(self, abort_on_exit: bool = True) -> bool:
        logger.info('Starting skaled from scratch')
        initial_status = True
        if is_container_exists(self.name, dutils=self.dutils):
            logger.info('Removing skaled container')
            remove_schain_container(self.name, dutils=self.dutils)
        else:
            logger.warning('Container doesn\'t exists')
        self.schain_record.set_restart_count(0)
        self.schain_record.set_failed_rpc_count(0)
        update_ssl_change_date(self.schain_record)
        self.schain_record.set_needs_reload(False)
        initial_status = self.skaled_container(
            abort_on_exit=abort_on_exit)
        return initial_status

    @BaseActionManager.monitor_block
    def recreated_schain_containers(self, abort_on_exit: bool = True) -> bool:
        logger.info('Restart skaled and IMA from scratch')
        initial_status = True
        # Remove IMA -> skaled, start skaled -> IMA
        if is_container_exists(self.name, container_type=IMA_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_ima_container(self.name, dutils=self.dutils)
        if is_container_exists(self.name, container_type=SCHAIN_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_schain_container(self.name, dutils=self.dutils)
        # Reseting restart counters
        self.schain_record.set_restart_count(0)
        self.schain_record.set_failed_rpc_count(0)
        self.schain_record.set_needs_reload(False)
        self.skaled_container(abort_on_exit=abort_on_exit)
        self.ima_container()
        return initial_status

    @BaseActionManager.monitor_block
    def skaled_rpc(self) -> bool:
        initial_status = self.checks.rpc.status
        if not initial_status:
            self.display_skaled_logs()
            logger.info('Handling schain rpc')
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

    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container.status
        migration_ts = get_ima_migration_ts(self.name)
        logger.debug('Migration time for %s IMA - %d', self.name, migration_ts)
        if not initial_status:
            pull_new_image(image_type=IMA_CONTAINER, dutils=self.dutils)
            ima_data = ImaData(
                linked=self.econfig.ima_linked,
                chain_id=self.econfig.chain_id
            )
            logger.info('Running IMA container watchman')
            monitor_ima_container(
                self.schain,
                ima_data,
                migration_ts=migration_ts,
                dutils=self.dutils
            )
        else:
            logger.info('ima_container - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def cleanup_schain_docker_entity(self) -> bool:
        logger.info('Removing skaled docker artifacts')
        remove_schain_container(self.name, dutils=self.dutils)
        time.sleep(SCHAIN_CLEANUP_TIMEOUT)
        remove_schain_volume(self.name, dutils=self.dutils)
        return True

    @BaseActionManager.monitor_block
    def update_config(self) -> bool:
        logger.info('Syncing skaled config with upstream')
        return self.cfm.sync_skaled_config_with_upstream()

    @BaseActionManager.monitor_block
    def schedule_skaled_exit(self, exit_ts: int) -> None:
        if self.skaled_status.exit_time_reached or self.esfm.exists():
            logger.info('Exit time has been already set')
            return
        if exit_ts is not None:
            logger.info('Scheduling skaled exit time %d', exit_ts)
            self.esfm.exit_ts = exit_ts

    @BaseActionManager.monitor_block
    def reset_exit_schedule(self) -> None:
        logger.info('Reseting exit schedule')
        if self.esfm.exists():
            self.esfm.rm()

    @BaseActionManager.monitor_block
    def disable_backup_run(self) -> None:
        logger.debug('Turning off backup mode')
        self.schain_record.set_backup_run(False)

    @property
    def upstream_config_path(self) -> Optional[str]:
        return self.cfm.latest_upstream_path

    @property
    def upstream_finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_latest_upstream(self.cfm)

    @property
    def finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_skaled_config(self.cfm)

    def display_skaled_logs(self) -> None:
        if is_container_exists(self.name, dutils=self.dutils):
            container_name = get_container_name(SCHAIN_CONTAINER, self.name)
            self.dutils.display_container_logs(container_name)
        else:
            logger.warning(
                f'sChain {self.name}: container doesn\'t exists, could not show logs')

    @BaseActionManager.monitor_block
    def notify_repair_mode(self) -> None:
        notify_repair_mode(
            self.node_config.all(),
            self.name
        )

    @BaseActionManager.monitor_block
    def disable_repair_mode(self) -> None:
        logger.info('Switching off repair mode')
        self.schain_record.set_repair_mode(False)
