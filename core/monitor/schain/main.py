#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2019 SKALE Labs
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
import os
import time
from importlib import reload
from typing import Optional

from skale import SkaleIma, SkaleManager
from skale.types.schain import SchainStructure
from web3._utils import http_session_manager

from core.chain.status import get_node_cli_status, get_skaled_status
from core.checks.base import TG_ALLOWED_CHECKS, get_api_checks_status
from core.checks.schain import SkaledChecks
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.static_params import get_automatic_repair_option
from core.firewall import get_default_rule_controller
from core.monitor.schain import get_skaled_monitor
from core.monitor.schain.action_skaled import SkaledActionManager
from core.monitor.schain.monitor_config import run_config_pipeline
from core.monitor.tasks import BaseTask, execute_tasks
from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.schains.external_config import ExternalConfig
from core.schains.process import ProcessReport
from tools.configs import PASSIVE_NODE
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from tools.configs.web3 import endpoint, manager_contracts
from tools.docker_utils import DockerUtils
from tools.helper import is_node_part_of_chain, no_hyphens
from tools.notifications.messages import notify_checks
from tools.resources import get_statsd_client
from tools.wallet_utils import init_wallet
from web.models.schain import SChainRecord, upsert_schain_record

logger = logging.getLogger(__name__)


def run_skaled_pipeline(
    schain: SchainStructure, node_config: NodeConfig, dutils: DockerUtils
) -> None:
    logger.info('Running skaled pipeline')
    logger.debug('Initializing schain record')
    schain_record = SChainRecord.get_by_name(schain.name)

    logger.info('Record: %s', SChainRecord.to_dict(schain_record))

    dutils = dutils or DockerUtils()

    rc = get_default_rule_controller(name=schain.name)
    logger.debug('Initializing skaled checks')
    skaled_checks = SkaledChecks(
        schain_name=schain.name,
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils,
        passive_node=PASSIVE_NODE,
    )

    logger.debug('Initializing skaled status')
    skaled_status = get_skaled_status(schain.name)
    logger.debug('Initializing node-cli status')
    ncli_status = get_node_cli_status(schain.name)

    logger.debug('Initializing skaled action manager')
    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        ncli_status=ncli_status,
        econfig=ExternalConfig(schain.name),
        dutils=dutils,
    )
    logger.debug('Gathering skaled status')
    check_status = skaled_checks.get_all(log=False, expose=True)
    logger.debug('Get automatic repair option')
    automatic_repair = get_automatic_repair_option()
    logger.debug('Creating api only check results')
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(schain.name, node_config.all(), api_status)

    logger.info('Skaled check status: %s', check_status)
    logger.info('Upstream config %s', skaled_am.upstream_config_path)

    mon = get_skaled_monitor(
        action_manager=skaled_am,
        check_status=check_status,
        schain_record=schain_record,
        skaled_status=skaled_status,
        ncli_status=ncli_status,
        automatic_repair=automatic_repair,
    )

    statsd_client = get_statsd_client()
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(schain.name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(schain.name)}'):
        mon(skaled_am, skaled_checks).run()


class SkaledTask(BaseTask):
    NAME = 'skaled'
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 1

    def __init__(
        self,
        schain: SchainStructure,
        node_config: NodeConfig,
        stream_version: str,
        dutils: Optional[DockerUtils] = None,
    ) -> None:
        self.schain = schain
        self.dutils = dutils or DockerUtils()
        super().__init__(
            chain_name=schain.name,
            node_config=node_config,
            stream_version=stream_version,
        )

    @property
    def stuck_timeout(self) -> int:
        return self.STUCK_TIMEOUT_SECONDS

    @property
    def needed(self) -> bool:
        chain_record = upsert_schain_record(self.chain_name)
        return chain_record.config_version == self.stream_version and (
            not chain_record.sync_config_run or not chain_record.first_run
        )

    def run(self) -> None:
        try:
            run_skaled_pipeline(
                schain=self.schain,
                node_config=self.node_config,
                dutils=self.dutils,
            )
        except Exception:
            logger.exception('Task %s failed', self.name)


class ConfigTask(BaseTask):
    NAME = 'config'
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 2
    POST_MONITOR_SLEEP_SECONDS = 300

    def __init__(
        self,
        schain: SchainStructure,
        skale: SkaleManager,
        skale_ima: SkaleIma,
        node_config: NodeConfig,
        stream_version: str,
    ) -> None:
        self.skale = skale
        self.skale_ima = skale_ima
        self.schain = schain
        super().__init__(
            chain_name=schain.name,
            node_config=node_config,
            stream_version=stream_version,
        )

    @property
    def stuck_timeout(self) -> int:
        dkg_timeout = self.skale.constants_holder.get_dkg_timeout()
        return int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    @property
    def needed(self) -> bool:
        return PASSIVE_NODE or is_node_part_of_chain(
            self.skale, self.chain_name, self.node_config.id
        )

    def run(self) -> None:
        try:
            run_config_pipeline(
                schain=self.schain,
                skale=self.skale,
                skale_ima=self.skale_ima,
                node_config=self.node_config,
                stream_version=self.stream_version,
            )
            logger.info('Sleeping %d seconds after monitor task', self.POST_MONITOR_SLEEP_SECONDS)
            time.sleep(self.POST_MONITOR_SLEEP_SECONDS)
        except Exception:
            logger.exception('Task %s failed', self.name)


def start_tasks(
    schain: SchainStructure,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    dutils: Optional[DockerUtils] = None,
) -> bool:
    reload(http_session_manager)

    wallet = init_wallet(node_config=node_config, endpoint=endpoint())
    skale = SkaleManager(endpoint(), manager_contracts(), wallet)

    name = schain.name
    init_ts, pid = int(time.time()), os.getpid()
    logger.info('Initializing process report %d %d', pid, init_ts)
    process_report = ProcessReport(name)
    process_report.update(pid, init_ts)

    stream_version = get_skale_node_version()
    schain_record = upsert_schain_record(name)

    is_rotation_active = skale.node_rotation.is_rotation_active(name)

    leaving_chain = not PASSIVE_NODE and not is_node_part_of_chain(skale, name, node_config.id)
    if leaving_chain and not is_rotation_active:
        logger.info('Not on node (%d), finishing process', node_config.id)
        return True

    logger.info(
        'sync_config_run %s, config_version %s, stream_version %s',
        schain_record.sync_config_run,
        schain_record.config_version,
        stream_version,
    )

    statsd_client = get_statsd_client()
    monitor_last_seen_ts = schain_record.monitor_last_seen.timestamp()
    statsd_client.incr(f'admin.schain.monitor.{no_hyphens(name)}')
    statsd_client.gauge(f'admin.schain.monitor_last_seen.{no_hyphens(name)}', monitor_last_seen_ts)

    if schain_record.config_version != stream_version or (
        schain_record.sync_config_run and schain_record.first_run
    ):
        logger.info('Fetching upstream config requested. Removing the old skaled config')
        ConfigFileManager(name).remove_skaled_config()

    tasks = [
        ConfigTask(
            schain=schain,
            skale=skale,
            skale_ima=skale_ima,
            node_config=node_config,
            stream_version=stream_version,
        ),
        SkaledTask(
            schain=schain,
            node_config=node_config,
            stream_version=stream_version,
            dutils=dutils,
        ),
    ]
    execute_tasks(tasks=tasks, process_report=process_report)
    return True
