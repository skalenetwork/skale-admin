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
from typing import Optional

from skale.types.schain import Schain

from core.chain.containers import monitor_ima_container, monitor_skaled_container
from core.chain.runner import (
    is_container_exists,
    pull_new_image,
    restart_container,
)
from core.chain.status import NodeCliStatus
from core.chain.volume import init_data_volume
from core.checks.schain import SkaledChecks
from core.config.endpoint import get_base_port_from_config
from core.config.schain.helper import (
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.config.schain.main import (
    get_finish_ts_from_latest_upstream,
    get_finish_ts_from_skaled_config,
)
from core.firewall import IRuleController
from core.ima.container import ImaData
from core.ima.container import get_migration_ts as get_ima_migration_ts
from core.monitor.action_base import (
    CONTAINER_POST_RUN_DELAY,
    BaseActionManager,
    BaseSkaledActionManager,
)
from core.node_config import NodeConfig
from core.schains.cleaner import remove_ima_container, remove_skaled_container
from core.schains.external_config import ExternalConfig
from core.schains.limits import get_schain_type
from tools.configs import PASSIVE_NODE
from tools.configs.containers import IMA_CONTAINER, SKALED_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import no_hyphens
from tools.node_options import NodeOptions
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord, upsert_schain_record

logger = logging.getLogger(__name__)


class SkaledActionManager(BaseSkaledActionManager):
    def __init__(
        self,
        schain: Schain,
        rule_controller: IRuleController,
        checks: SkaledChecks,
        node_config: NodeConfig,
        ncli_status: NodeCliStatus,
        econfig: Optional[ExternalConfig] = None,
        dutils: DockerUtils | None = None,
        node_options: NodeOptions | None = None,
        post_run_delay: int = CONTAINER_POST_RUN_DELAY,
    ):
        super().__init__(
            chain_name=schain.name,
            rule_controller=rule_controller,
            checks=checks,
            node_config=node_config,
            dutils=dutils,
            node_options=node_options,
            post_run_delay=post_run_delay,
        )

        self.schain = schain
        self.chain_name = schain.name
        self.generation = schain.generation
        self.checks = checks
        self.schain_type = get_schain_type(schain.part_of_node)
        self.econfig = econfig or ExternalConfig(schain.name)
        self.statsd_client = get_statsd_client()
        self.ncli_status = ncli_status

    @property
    def chain_record(self) -> SChainRecord:
        return upsert_schain_record(self.name)

    @BaseActionManager.monitor_block
    def skaled_container(
        self,
        download_snapshot: bool = False,
        start_ts: Optional[int] = None,
        abort_on_exit: bool = True,
        passive_node: bool = PASSIVE_NODE,
    ) -> bool:
        logger.info(
            'Starting skaled container watchman snapshot: %s, start_ts: %s',
            download_snapshot,
            start_ts,
        )
        snapshot_from = self.ncli_status.snapshot_from if self.ncli_status else None
        monitor_skaled_container(
            self.chain_name,
            chain_record=self.chain_record,
            skaled_status=self.skaled_status,
            download_snapshot=download_snapshot,
            snapshot_from=snapshot_from,
            start_ts=start_ts,
            abort_on_exit=abort_on_exit,
            dutils=self.dutils,
            passive_node=passive_node,
            historic_state=self.node_options.historic_state,
        )
        time.sleep(self.post_run_delay)
        return True

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            logger.info('Creating volume')
            init_data_volume(self.schain, passive_node=PASSIVE_NODE, dutils=self.dutils)
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
            with self.statsd_client.timer(f'admin.action.firewall.{no_hyphens(self.name)}'):
                self.rule_controller.configure(
                    base_port=base_port, own_ip=own_ip, node_ips=node_ips, sync_ip_ranges=ranges
                )
                self.statsd_client.gauge(
                    f'admin.action.expected_rules.{no_hyphens(self.name)}',
                    len(self.rule_controller.expected_rules()),
                )
                self.rule_controller.sync()
        return initial_status

    @BaseActionManager.monitor_block
    def restart_ima_container(self) -> bool:
        initial_status = True
        if is_container_exists(self.name, container_type=IMA_CONTAINER, dutils=self.dutils):
            logger.info('IMA container exists, restarting')
            restart_container(IMA_CONTAINER, self.chain_name, dutils=self.dutils)
        else:
            logger.info("IMA container doesn't exists, running skaled watchman")
            initial_status = self.ima_container()
        return initial_status

    @BaseActionManager.monitor_block
    def recreated_chain_containers(self, abort_on_exit: bool = True) -> bool:
        logger.info('Restart skaled and IMA from scratch')
        initial_status = True
        # Remove IMA -> skaled, start skaled -> IMA
        if is_container_exists(self.name, container_type=IMA_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_ima_container(self.name, dutils=self.dutils)
        if is_container_exists(self.name, container_type=SKALED_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_skaled_container(self.name, dutils=self.dutils)
        # Resetting restart counters
        self.chain_record.set_restart_count(0)
        self.chain_record.set_failed_rpc_count(0)
        self.skaled_container(abort_on_exit=abort_on_exit)
        self.ima_container()
        return initial_status

    def ima_container(self) -> bool:
        initial_status = self.checks.ima_container.status
        migration_ts = get_ima_migration_ts(self.name)
        logger.debug('Migration time for %s IMA - %d', self.name, migration_ts)
        if not initial_status:
            pull_new_image(image_type=IMA_CONTAINER, dutils=self.dutils)
            ima_data = ImaData(linked=self.econfig.ima_linked, chain_id=self.econfig.chain_id)
            logger.info('Running IMA container watchman')
            monitor_ima_container(
                self.chain_name, ima_data, migration_ts=migration_ts, dutils=self.dutils
            )
        else:
            logger.info('ima_container - ok')
        return initial_status

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
        logger.info('Resetting exit schedule')
        if self.esfm.exists():
            self.esfm.rm()

    @BaseActionManager.monitor_block
    def disable_backup_run(self) -> None:
        logger.debug('Turning off backup mode')
        self.chain_record.set_backup_run(False)

    @property
    def upstream_finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_latest_upstream(self.cfm)

    @property
    def finish_ts(self) -> Optional[int]:
        return get_finish_ts_from_skaled_config(self.cfm)
