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
from typing import Optional, cast
from importlib import reload

from skale import SkaleManager, SkaleIma
from skale.types.schain import SchainName, SchainStructure
from web3._utils import http_session_manager

from core.monitor.schain.monitor_config import run_config_pipeline
from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.checks.schain import SkaledChecks
from core.checks.base import get_api_checks_status, TG_ALLOWED_CHECKS
from core.config.schain.file_manager import ConfigFileManager
from core.config.schain.static_params import get_automatic_repair_option
from core.firewall import get_default_rule_controller
from core.schains.external_config import ExternalConfig
from core.monitor.schain import get_skaled_monitor

from core.monitor.schain.action_skaled import SkaledActionManager

from core.monitor.tasks import BaseTask, execute_tasks
from core.schains.process import ProcessReport
from core.chain.status import get_node_cli_status, get_skaled_status

from tools.docker_utils import DockerUtils
from tools.configs import PASSIVE_NODE
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from tools.notifications.messages import notify_checks
from tools.helper import is_node_part_of_chain, no_hyphens
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord, upsert_schain_record


logger = logging.getLogger(__name__)


def run_skaled_pipeline(
    schain_name: SchainName, skale: SkaleManager, node_config: NodeConfig, dutils: DockerUtils
) -> None:
    schain = skale.schains.get_by_name(schain_name)
    logger.info('Initializing schain record')
    schain_record = SChainRecord.get_by_name(schain_name)

    logger.info('Record: %s', SChainRecord.to_dict(schain_record))

    dutils = dutils or DockerUtils()

    rc = get_default_rule_controller(name=schain_name)
    logger.info('Initializing skaled checks')
    skaled_checks = SkaledChecks(
        schain_name=schain.name,
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils,
        passive_node=PASSIVE_NODE,
    )

    logger.info('Initializing skaled status')
    skaled_status = get_skaled_status(schain_name)
    logger.info('Initializing node-cli status')
    ncli_status = get_node_cli_status(schain_name)

    logger.info('Initializing skaled action manager')
    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        ncli_status=ncli_status,
        econfig=ExternalConfig(schain_name),
        dutils=dutils,
    )
    logger.info('Gathering skaled status')
    check_status = skaled_checks.get_all(log=False, expose=True)
    logger.info('Get automatic repair option')
    automatic_repair = get_automatic_repair_option()
    logger.info('Creating api only check results')
    api_status = get_api_checks_status(status=check_status, allowed=TG_ALLOWED_CHECKS)
    notify_checks(schain_name, node_config.all(), api_status)

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
    statsd_client.incr(f'admin.skaled_pipeline.{mon.__name__}.{no_hyphens(schain_name)}')
    with statsd_client.timer(f'admin.skaled_pipeline.duration.{no_hyphens(schain_name)}'):
        mon(skaled_am, skaled_checks).run()


class SkaledTask(BaseTask):
    NAME = 'skaled'
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 1

    def __init__(
        self,
        chain_name: SchainName,
        skale: SkaleManager,
        node_config: NodeConfig,
        stream_version: str,
        dutils: Optional[DockerUtils] = None,
    ) -> None:
        self.skale = skale
        self.dutils = dutils
        super().__init__(
            chain_name=chain_name,
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
                schain_name=cast(SchainName, self.chain_name),
                skale=self.skale,
                node_config=self.node_config,
                dutils=self.dutils,
            )
        except Exception:
            logger.exception('Task %s failed', self.name)


class ConfigTask(BaseTask):
    NAME = 'config'
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 2

    def __init__(
        self,
        schain_name: SchainName,
        skale: SkaleManager,
        skale_ima: SkaleIma,
        node_config: NodeConfig,
        stream_version: str,
    ) -> None:
        self.skale = skale
        self.skale_ima = skale_ima
        super().__init__(
            chain_name=schain_name,
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
                schain_name=self.chain_name,
                skale=self.skale,
                skale_ima=self.skale_ima,
                node_config=self.node_config,
                stream_version=self.stream_version,
            )
        except Exception:
            logger.exception('Task %s failed', self.name)


def start_tasks(
    skale: SkaleManager,
    schain: SchainStructure,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    dutils: Optional[DockerUtils] = None,
) -> bool:
    reload(http_session_manager)

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
            schain_name=schain.name,
            skale=skale,
            skale_ima=skale_ima,
            node_config=node_config,
            stream_version=stream_version,
        ),
        SkaledTask(
            chain_name=schain.name,
            skale=skale,
            node_config=node_config,
            stream_version=stream_version,
            dutils=dutils,
        ),
    ]
    execute_tasks(tasks=tasks, process_report=process_report)
    return True
