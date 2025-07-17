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
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from core.chain.containers import monitor_skaled_container
from core.chain.runner import is_container_exists
from core.chain.volume import init_fair_volume
from core.checks.fair import SkaledChecks
from core.config.endpoint import get_base_port_from_config
from core.config.fair.firewall import (
    get_node_ips_from_config,
    get_own_ip_from_config,
)
from core.config.fair.helper import random_timestamp_between
from core.firewall import FairCommitteeScopeRuleController
from core.monitor.action_base import (
    CONTAINER_POST_RUN_DELAY,
    BaseActionManager,
    BaseSkaledActionManager,
)
from core.node_config import NodeConfig
from core.schains.cleaner import remove_skaled_container
from core.types.chain import FairChainName
from tools.configs.containers import SKALED_CONTAINER, SKALED_RESTART_DELAY_SECONDS
from tools.docker_utils import DockerUtils
from tools.node_options import NodeOptions

logger = logging.getLogger(__name__)


class FairSkaledActionManager(BaseSkaledActionManager):
    def __init__(
        self,
        chain_name: FairChainName,
        rule_controller: FairCommitteeScopeRuleController,
        checks: SkaledChecks,
        node_config: NodeConfig,
        scheduler: BackgroundScheduler,
        dutils: DockerUtils | None = None,
        node_options: NodeOptions | None = None,
    ):
        super().__init__(
            chain_name=chain_name,
            rule_controller=rule_controller,
            checks=checks,
            node_config=node_config,
            dutils=dutils,
            node_options=node_options,
        )
        self.chain_name = chain_name
        self.scheduler = scheduler

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
            start_ts,
        )

        # node_in_current_config = is_node_in_current_config_group(
        #     self.cfm.skaled_config, self.node_config.id
        # )
        sync_node = False  # todod: tmp, handle it later

        monitor_skaled_container(
            self.chain_name,
            chain_record=self.chain_record,
            skaled_status=self.skaled_status,
            download_snapshot=download_snapshot,
            snapshot_from=self.chain_record.snapshot_from,
            start_ts=start_ts,
            abort_on_exit=abort_on_exit,
            dutils=self.dutils,
            sync_node=sync_node,  # todod: tmp, handle it later - skaled should be fixed
            historic_state=self.node_options.historic_state,
        )
        time.sleep(CONTAINER_POST_RUN_DELAY)
        return True

    @BaseActionManager.monitor_block
    def volume(self) -> bool:
        initial_status = self.checks.volume.status
        if not initial_status:
            logger.info('Creating volume')
            init_fair_volume(self.chain_name, dutils=self.dutils)
        else:
            logger.info('Volume - ok')
        return initial_status

    @BaseActionManager.monitor_block
    def recreated_schain_containers(self, abort_on_exit: bool = True) -> bool:
        logger.info('Restart skaled from scratch')
        initial_status = True
        if is_container_exists(self.name, container_type=SKALED_CONTAINER, dutils=self.dutils):
            initial_status = False
            remove_skaled_container(self.name, dutils=self.dutils)
        self.chain_record.set_restart_count(0)
        self.chain_record.set_failed_rpc_count(0)
        self.skaled_container(abort_on_exit=abort_on_exit)
        return initial_status

    @BaseActionManager.monitor_block
    def committee_scope_firewall_rules(self, upstream: bool = False) -> bool:
        initial_status = self.checks.committee_scope_firewall_rules.status
        if not initial_status:
            logger.info('Configuring committee scope firewall rules')

            conf = self.cfm.latest_upstream_config if upstream else self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            node_ips = get_node_ips_from_config(conf)
            own_ip = get_own_ip_from_config(conf)

            self.rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
            self.rule_controller.sync()
        return initial_status

    @BaseActionManager.monitor_block
    def schedule_skaled_restart(self, last_group_start_timestamp: int) -> bool:
        logger.info('Scheduling skaled restart')
        # TODOD: add more robust way to ensure that skaled is always restarted:
        time_now = datetime.now()
        earliest_possible_restart_ts = int(time_now.timestamp())
        latest_possible_restart_ts = last_group_start_timestamp - SKALED_RESTART_DELAY_SECONDS
        logger.info(
            'Scheduling skaled restart between %d and %d, last_group_start_timestamp: %d',
            earliest_possible_restart_ts,
            latest_possible_restart_ts,
            last_group_start_timestamp,
        )
        restart_ts = random_timestamp_between(
            earliest_possible_restart_ts, latest_possible_restart_ts
        )
        self.chain_record.set_restart_ts(restart_ts)
        logger.info('Scheduling skaled restart at %d', restart_ts)
        self.scheduler.add_job(
            func=self.recreated_schain_containers,
            trigger='date',
            run_date=datetime.fromtimestamp(restart_ts),
        )
        return True
