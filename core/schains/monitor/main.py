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

import functools
import logging
import os
import time
from typing import Callable, Optional
from importlib import reload

from skale import Skale, SkaleIma
from skale.contracts.manager.schains import SchainStructure
from web3._utils import request as web3_request

from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.schains.checks import ConfigChecks, get_api_checks_status, TG_ALLOWED_CHECKS, SkaledChecks
from core.schains.config.file_manager import ConfigFileManager
from core.schains.config.static_params import get_automatic_repair_option
from core.schains.firewall import get_default_rule_controller
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.external_config import ExternalConfig, ExternalState
from core.schains.monitor import get_skaled_monitor, RegularConfigMonitor, SyncConfigMonitor
from core.schains.monitor.action import ConfigActionManager, SkaledActionManager
from core.schains.monitor.tasks import execute_tasks, Future, ITask
from core.schains.process import ProcessReport
from core.schains.status import get_node_cli_status, get_skaled_status
from core.node import get_current_nodes

from tools.docker_utils import DockerUtils
from tools.configs import SYNC_NODE
from tools.configs.schains import DKG_TIMEOUT_COEFFICIENT
from tools.notifications.messages import notify_checks
from tools.helper import is_node_part_of_chain, no_hyphens
from tools.resources import get_statsd_client
from web.models.schain import SChainRecord, upsert_schain_record


MIN_SCHAIN_MONITOR_SLEEP_INTERVAL = 20
MAX_SCHAIN_MONITOR_SLEEP_INTERVAL = 40

STUCK_TIMEOUT = 60 * 60 * 2
SHUTDOWN_INTERVAL = 60 * 10

logger = logging.getLogger(__name__)


class NoTasksToRunError(Exception):
    pass


def run_config_pipeline(
    schain_name: str,
    skale: Skale,
    skale_ima: SkaleIma,
    node_config: NodeConfig,
    stream_version: str,
) -> None:
    schain = skale.schains.get_by_name(schain_name)
    schain_record = SChainRecord.get_by_name(schain_name)
    rotation_data = skale.node_rotation.get_rotation(schain_name)
    allowed_ranges = get_sync_agent_ranges(skale)
    ima_linked = not SYNC_NODE and skale_ima.linker.has_schain(schain_name)
    group_index = skale.schains.name_to_group_id(schain_name)
    last_dkg_successful = skale.dkg.is_last_dkg_successful(group_index)
    current_nodes = get_current_nodes(skale, schain_name)

    estate = ExternalState(
        ima_linked=ima_linked, chain_id=skale_ima.web3.eth.chain_id, ranges=allowed_ranges
    )
    econfig = ExternalConfig(schain_name)
    config_checks = ConfigChecks(
        schain_name=schain_name,
        node_id=node_config.id,
        schain_record=schain_record,
        stream_version=stream_version,
        rotation_id=rotation_data['rotation_id'],
        current_nodes=current_nodes,
        last_dkg_successful=last_dkg_successful,
        econfig=econfig,
        estate=estate,
    )

    config_am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=stream_version,
        checks=config_checks,
        current_nodes=current_nodes,
        estate=estate,
        econfig=econfig,
    )

    status = config_checks.get_all(log=False, expose=True)
    logger.info('Config checks: %s', status)

    if SYNC_NODE:
        logger.info(
            'Sync node last_dkg_successful %s, rotation_data %s', last_dkg_successful, rotation_data
        )
        mon = SyncConfigMonitor(config_am, config_checks)
    else:
        logger.info('Regular node mode, running config monitor')
        mon = RegularConfigMonitor(config_am, config_checks)
    statsd_client = get_statsd_client()

    statsd_client.incr(f'admin.config_pipeline.{mon.__class__.__name__}.{no_hyphens(schain_name)}')
    statsd_client.gauge(
        f'admin.config_pipeline.rotation_id.{no_hyphens(schain_name)}', rotation_data['rotation_id']
    )
    with statsd_client.timer(f'admin.config_pipeline.duration.{no_hyphens(schain_name)}'):
        mon.run()


def run_skaled_pipeline(
    schain_name: str, skale: Skale, node_config: NodeConfig, dutils: DockerUtils
) -> None:
    schain = skale.schains.get_by_name(schain_name)
    schain_record = SChainRecord.get_by_name(schain_name)

    logger.info('Record: %s', SChainRecord.to_dict(schain_record))

    dutils = dutils or DockerUtils()

    rc = get_default_rule_controller(name=schain_name)
    skaled_checks = SkaledChecks(
        schain_name=schain.name,
        schain_record=schain_record,
        rule_controller=rc,
        dutils=dutils,
        sync_node=SYNC_NODE,
    )

    skaled_status = get_skaled_status(schain_name)
    ncli_status = get_node_cli_status(schain_name)

    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rc,
        checks=skaled_checks,
        node_config=node_config,
        ncli_status=ncli_status,
        econfig=ExternalConfig(schain_name),
        dutils=dutils,
    )
    check_status = skaled_checks.get_all(log=False, expose=True)
    automatic_repair = get_automatic_repair_option()
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


class SkaledTask(ITask):
    NAME = 'skaled'
    STUCK_TIMEOUT = 3600  # 1 hour

    def __init__(
        self,
        schain_name: str,
        skale: Skale,
        node_config: NodeConfig,
        stream_version: str,
        dutils: Optional[DockerUtils] = None,
    ) -> None:
        self.schain_name = schain_name
        self.skale = skale
        self.node_config = node_config
        self.dutils = dutils
        self._future = Future()
        self._start_ts = 0
        self.stream_version = stream_version

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def stuck_timeout(self) -> int:
        return self.STUCK_TIMEOUT

    @property
    def future(self) -> Future:
        return self._future

    @future.setter
    def future(self, value: Future) -> None:
        self._future = value

    @property
    def start_ts(self) -> int:
        return self._start_ts

    @start_ts.setter
    def start_ts(self, value: int) -> None:
        self._start_ts = value

    @property
    def needed(self) -> bool:
        schain_record = upsert_schain_record(self.schain_name)
        return schain_record.config_version == self.stream_version and (
            not schain_record.sync_config_run or not schain_record.first_run
        )

    def create_pipeline(self) -> Callable:
        return functools.partial(
            run_skaled_pipeline,
            schain_name=self.schain_name,
            skale=self.skale,
            node_config=self.node_config,
            dutils=self.dutils,
        )


class ConfigTask(ITask):
    NAME = 'config'
    STUCK_TIMEOUT = 60 * 60 * 2

    def __init__(
        self,
        schain_name: str,
        skale: Skale,
        skale_ima: SkaleIma,
        node_config: NodeConfig,
        stream_version: str,
    ) -> None:
        self.schain_name = schain_name
        self.skale = skale
        self.skale_ima = skale_ima
        self.node_config = node_config
        self.stream_version = stream_version
        self._start_ts = 0
        self._future = Future()

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def future(self) -> Future:
        return self._future

    @future.setter
    def future(self, value: Future) -> None:
        self._future = value

    @property
    def stuck_timeout(self) -> int:
        dkg_timeout = self.skale.constants_holder.get_dkg_timeout()
        return int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    @property
    def start_ts(self) -> int:
        return self._start_ts

    @start_ts.setter
    def start_ts(self, value: int) -> None:
        self._start_ts = value

    @property
    def needed(self) -> bool:
        return SYNC_NODE or is_node_part_of_chain(self.skale, self.schain_name, self.node_config.id)

    def create_pipeline(self) -> Callable:
        return functools.partial(
            run_config_pipeline,
            schain_name=self.schain_name,
            skale=self.skale,
            skale_ima=self.skale_ima,
            node_config=self.node_config,
            stream_version=self.stream_version,
        )


def start_tasks(
    skale: Skale,
    schain: SchainStructure,
    node_config: NodeConfig,
    skale_ima: SkaleIma,
    dutils: Optional[DockerUtils] = None,
) -> bool:
    reload(web3_request)

    name = schain.name
    init_ts, pid = int(time.time()), os.getpid()
    logger.info('Initialazing process report %d %d', pid, init_ts)
    process_report = ProcessReport(name)
    process_report.update(pid, init_ts)

    stream_version = get_skale_node_version()
    schain_record = upsert_schain_record(name)

    is_rotation_active = skale.node_rotation.is_rotation_active(name)

    leaving_chain = not SYNC_NODE and not is_node_part_of_chain(skale, name, node_config.id)
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
            schain_name=schain.name,
            skale=skale,
            node_config=node_config,
            stream_version=stream_version,
            dutils=dutils
        ),
    ]
    execute_tasks(tasks=tasks, process_report=process_report)
