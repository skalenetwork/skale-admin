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
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from core.chain.containers import monitor_skaled_container
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
from core.types.chain import FairChainName
from tools.configs.containers import SKALED_RESTART_DELAY_SECONDS
from tools.configs.fair import SKALED_RESTART_JOB_NAME
from tools.docker_utils import DockerUtils
from tools.node_options import NodeOptions

logger = logging.getLogger(__name__)


class FairSkaledActionManager(BaseSkaledActionManager):
    checks: SkaledChecks
    rule_controller: FairCommitteeScopeRuleController

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
        passive_node: bool = False,
        abort_on_exit: bool = True,
    ) -> bool:
        snapshot_from = None
        if self.chain_record.snapshot_from:
            logger.info(
                'Skaled start mode: snapshot, snapshot_from: %s', self.chain_record.snapshot_from
            )
            download_snapshot = True
            if self.chain_record.snapshot_from != 'any':
                snapshot_from = self.chain_record.snapshot_from
        else:
            logger.info('Skaled start mode: regular')

        monitor_skaled_container(
            self.chain_name,
            chain_record=self.chain_record,
            skaled_status=self.skaled_status,
            download_snapshot=download_snapshot,
            snapshot_from=snapshot_from,
            abort_on_exit=abort_on_exit,
            dutils=self.dutils,
            passive_node=passive_node,
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
    def committee_scope_firewall_rules(self, upstream: bool = False) -> bool:
        initial_status = self.checks.committee_scope_firewall_rules.status
        if not initial_status:
            logger.info('Configuring committee scope firewall rules')

            conf = self.cfm.latest_upstream_config if upstream else self.cfm.skaled_config
            base_port = get_base_port_from_config(conf)
            current_ts = int(time.time())
            node_ips = get_node_ips_from_config(conf, current_ts)
            own_ip = get_own_ip_from_config(conf, current_ts)

            self.rule_controller.configure(base_port=base_port, own_ip=own_ip, node_ips=node_ips)
            self.rule_controller.sync()
        return initial_status

    @BaseActionManager.monitor_block
    def schedule_skaled_restart(self, restart_deadline: int) -> bool:
        logger.info('Scheduling skaled restart')
        earliest_possible_restart_ts = int(time.time())
        latest_possible_restart_ts = restart_deadline - SKALED_RESTART_DELAY_SECONDS
        logger.info(
            'Scheduling skaled restart between %d and %d, restart_deadline: %d',
            earliest_possible_restart_ts,
            latest_possible_restart_ts,
            restart_deadline,
        )
        restart_ts = random_timestamp_between(
            earliest_possible_restart_ts, latest_possible_restart_ts
        )
        self.chain_record.set_restart_ts(restart_ts)
        logger.info(
            'Scheduling skaled restart at %d, job id: %s', restart_ts, SKALED_RESTART_JOB_NAME
        )
        self.scheduler.add_job(
            func=self.recreated_skaled_container,
            trigger='date',
            run_date=datetime.fromtimestamp(restart_ts, tz=timezone.utc),
            id=SKALED_RESTART_JOB_NAME,
            name='skaled restart job',
        )
        return True
