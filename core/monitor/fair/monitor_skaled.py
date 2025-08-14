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
from typing import Type, cast

from apscheduler.schedulers.background import BackgroundScheduler

from core.chain.ssl import ssl_reload_needed
from core.chain.status import SkaledStatus, get_skaled_status
from core.checks.base import TG_ALLOWED_CHECKS, get_api_checks_status
from core.checks.fair import SkaledChecks
from core.config.fair.committee_nodes import get_last_group_start_timestamp_from_config
from core.firewall.utils import get_fair_committee_scope_rule_controller
from core.monitor.fair.action_skaled import FairSkaledActionManager
from core.monitor.monitor_base import BaseSkaledMonitor
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.types.chain import FairChainName
from tools.configs import PASSIVE_NODE
from tools.configs.fair import SKALED_RESTART_JOB_NAME
from tools.docker_utils import DockerUtils
from tools.helper import no_hyphens
from tools.notifications.messages import notify_checks
from tools.resources import get_statsd_client

logger = logging.getLogger(__name__)


def run_skaled_pipeline(
    chain_name: FairChainName,
    node_config: NodeConfig,
    scheduler: BackgroundScheduler,
    dutils: DockerUtils | None = None,
) -> None:
    logger.info('Initializing chain record')
    chain_record = ChainRecord(name=chain_name)
    if not chain_record:
        raise ValueError(f'Chain record for {chain_name} not found')
    logger.info('Record: %s', chain_record.to_dict())

    dutils = dutils or DockerUtils()

    rule_controller = get_fair_committee_scope_rule_controller()
    logger.info('Initializing skaled checks')
    skaled_checks = SkaledChecks(
        chain_name=chain_name,
        chain_record=chain_record,
        rule_controller=rule_controller,
        dutils=dutils,
        passive_node=PASSIVE_NODE,
    )

    logger.info('Initializing skaled status')
    skaled_status = get_skaled_status(chain_name)

    logger.info('Initializing skaled action manager')
    skaled_am = FairSkaledActionManager(
        chain_name=chain_name,
        rule_controller=rule_controller,
        checks=skaled_checks,
        node_config=node_config,
        scheduler=scheduler,
        dutils=dutils,
    )

    logger.info('Gathering skaled status')
    check_status = skaled_checks.get_all(log=False, expose=True)

    logger.info('Get automatic repair option')
    logger.info('Creating api only check results')
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(chain_name, node_config.all(), api_status)

    logger.info('Skaled check status: %s', check_status)
    logger.info('Upstream config: %s', skaled_am.upstream_config_path)

    mon = get_skaled_monitor(
        action_manager=skaled_am,
        check_status=check_status,
        chain_record=chain_record,
        skaled_status=skaled_status,
    )

    statsd_client = get_statsd_client()
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(chain_name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(chain_name)}'):
        mon(action_manager=skaled_am).run()


class BaseFairSkaledMonitor(BaseSkaledMonitor):
    def __init__(self, action_manager: FairSkaledActionManager) -> None:
        self._am: FairSkaledActionManager = action_manager
        self._checks = action_manager.checks

    @property
    def am(self) -> FairSkaledActionManager:
        return self._am

    @property
    def checks(self) -> SkaledChecks:
        return cast(SkaledChecks, self._checks)


class RegularSkaledMonitor(BaseFairSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.committee_scope_firewall_rules:
            self.am.committee_scope_firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            self.am.skaled_container(passive_node=PASSIVE_NODE)
        else:
            self.am.reset_restart_counter()
        if not self.checks.rpc:
            self.am.skaled_rpc()


class NoConfigSkaledMonitor(BaseFairSkaledMonitor):
    def execute(self):
        if self.checks.upstream_exists:
            logger.info('Creating skaled config')
            self.am.update_config()
        else:
            logger.debug('Waiting for upstream config')


class StartupSkaledMonitor(BaseFairSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.committee_scope_firewall_rules:
            self.am.committee_scope_firewall_rules()
        if not self.checks.volume:
            self.am.volume()
        if not self.checks.skaled_container:
            download_snapshot = True
            if PASSIVE_NODE and not self.am.chain_record.snapshot_from:
                download_snapshot = False
            self.am.skaled_container(download_snapshot=download_snapshot, passive_node=PASSIVE_NODE)
        else:
            self.am.reset_restart_counter()
        if not self.checks.rpc:
            self.am.skaled_rpc()


class UpdateConfigSkaledMonitor(BaseFairSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.config_updated:
            self.am.update_config()
        if not self.checks.committee_scope_firewall_rules:
            self.am.committee_scope_firewall_rules()
        last_group_start_timestamp = get_last_group_start_timestamp_from_config(
            self.am.cfm.latest_upstream_config
        )
        self.am.schedule_skaled_restart(last_group_start_timestamp)


class RecreateSkaledMonitor(BaseFairSkaledMonitor):
    def execute(self) -> None:
        if not self.checks.config_updated:
            self.am.update_config()
        if not self.checks.committee_scope_firewall_rules:
            self.am.committee_scope_firewall_rules()
        self.am.recreated_skaled_container()


def get_skaled_monitor(
    action_manager: FairSkaledActionManager,
    check_status: dict,
    chain_record: ChainRecord,
    skaled_status: SkaledStatus | None,
) -> Type[BaseFairSkaledMonitor]:
    logger.info('Choosing skaled monitor')
    if skaled_status:
        skaled_status.log()

    mon_type: Type[BaseFairSkaledMonitor] = RegularSkaledMonitor

    if (
        chain_record.restart_ts is not None
        and chain_record.restart_ts > 0
        and not action_manager.scheduler.get_job(SKALED_RESTART_JOB_NAME)
    ):
        logger.warning('Chain record restart timestamp is not zero and no restart job found')
        mon_type = UpdateConfigSkaledMonitor

    if not check_status['config']:
        mon_type = NoConfigSkaledMonitor
    elif check_status['skaled_container'] and ssl_reload_needed(chain_record):
        mon_type = RecreateSkaledMonitor
    elif not check_status['volume']:
        mon_type = StartupSkaledMonitor
    elif not check_status['config_updated']:
        mon_type = UpdateConfigSkaledMonitor
    return mon_type
