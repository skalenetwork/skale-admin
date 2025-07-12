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
from abc import abstractmethod
from apscheduler.schedulers.background import BackgroundScheduler

from skale import MirageManager

from core.checks.mirage import MirageConfigChecks
from core.monitor.mirage.action_config import MirageConfigActionManager
from core.monitor.mirage.healthcheck import handle_healthcheck_job
from core.monitor.monitor_base import IMonitor
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.types.chain import MirageChainName

from tools.helper import no_hyphens
from tools.resources import get_statsd_client

logger = logging.getLogger(__name__)


def run_config_pipeline(
    chain_name: MirageChainName,
    mirage: MirageManager,
    node_config: NodeConfig,
    stream_version: str,
    scheduler: BackgroundScheduler,
) -> None:
    logger.info('Running config pipeline for %s', chain_name)

    is_healthy = mirage.status.is_healthy(node_id=node_config.id)
    logger.info('Node health status: %s', is_healthy)
    handle_healthcheck_job(scheduler, node_config)

    committee_index = mirage.committee.get_active_committee_index()
    is_committee_node = mirage.committee.is_node_in_current_or_next_committee(node_config.id)

    logger.info(
        'Running config pipeline, committee index: %s, is committee node: %s',
        committee_index,
        is_committee_node,
    )

    chain_record = ChainRecord(chain_name)
    logger.info('Chain record: %s', chain_record)

    logger.info('Initializing config checks')
    config_checks = MirageConfigChecks(
        mirage=mirage,
        node_config=node_config,
        chain_name=chain_name,
        stream_version=stream_version,
        committee_index=committee_index,
        chain_record=chain_record,
    )

    logger.info('Initializing config action manager')
    config_am = MirageConfigActionManager(
        mirage=mirage,
        chain_name=chain_name,
        committee_index=committee_index,
        node_config=node_config,
        stream_version=stream_version,
        checks=config_checks,
    )

    logger.info('Gathering config status')
    status = config_checks.get_all(log=False, expose=True)
    logger.info('Config status: %s', status)

    if is_committee_node:
        logger.info('Committee node mode, running config monitor')
        mon = CommitteeConfigMonitor(config_am, config_checks)
    else:
        logger.info('Active node mode, running sync config monitor')
        mon = ActiveConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(chain_name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(chain_name)}',
        committee_index,
    )
    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(chain_name)}'):
        mon.run()


class BaseConfigMonitor(IMonitor):
    def __init__(
        self, action_manager: MirageConfigActionManager, checks: MirageConfigChecks
    ) -> None:
        self.am = action_manager
        self.checks = checks

    @abstractmethod
    def execute(self) -> None:
        pass

    def run(self):
        typename = type(self).__name__
        logger.info('Config monitor type starting %s', typename)
        try:
            self.am._upd_last_seen()
            self.execute()
            self.am.log_executed_blocks()
            self.am._upd_last_seen()
        except Exception as e:
            logger.info('Config monitor type failed %s', typename, exc_info=e)
        finally:
            logger.info('Config monitor type finished %s', typename)


class CommitteeConfigMonitor(BaseConfigMonitor):
    def execute(self) -> None:
        if not self.checks.config_dir:
            self.am.config_dir()
        if not self.checks.dkg:
            self.am.dkg()
        if not self.checks.upstream_config:
            self.am.upstream_config(is_committee_node=True)
        if not self.checks.network_scope_firewall_rules:
            self.am.network_scope_firewall_rules()
        self.am.reset_config_record()


class ActiveConfigMonitor(BaseConfigMonitor):
    def execute(self) -> None:
        if not self.checks.config_dir:
            self.am.config_dir()
        if not self.checks.upstream_config:
            self.am.upstream_config(is_committee_node=False)
        if not self.checks.network_scope_firewall_rules:
            self.am.network_scope_firewall_rules()
        self.am.reset_config_record()
