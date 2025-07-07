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
import os
import time
from typing import Optional, cast

from core.config.schain.static_params import get_mirage_chain_name
from core.monitor.mirage.monitor_config import run_config_pipeline
from core.monitor.mirage.monitor_skaled import run_skaled_pipeline
from core.monitor.tasks import BaseTask, execute_tasks
from core.node import get_skale_node_version
from core.node_config import NodeConfig
from core.redis.chain_record import ChainRecord
from core.schains.process import ProcessReport
from core.types.chain import MirageChainName
from core.utils.mirage import init_mirage_manager
from tools.docker_utils import DockerUtils

logger = logging.getLogger(__name__)


class ConfigTask(BaseTask):
    NAME = 'config'
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 2

    def __init__(
        self,
        chain_name: MirageChainName,
        node_config: NodeConfig,
        stream_version: str,
    ) -> None:
        super().__init__(
            chain_name=chain_name,
            node_config=node_config,
            stream_version=stream_version,
        )

    @property
    def stuck_timeout(self) -> int:
        return 100000  # TODOD: implement - use new dkg timeout
        # dkg_timeout = self.skale.constants_holder.get_dkg_timeout()
        # return int(dkg_timeout * DKG_TIMEOUT_COEFFICIENT)

    @property
    def needed(self) -> bool:
        return True

    def run(self) -> None:
        try:
            mirage = init_mirage_manager(node_config=self.node_config)
            run_config_pipeline(
                chain_name=cast(MirageChainName, self.chain_name),
                mirage=mirage,
                node_config=self.node_config,
                stream_version=self.stream_version,
            )
        except Exception:
            logger.exception('Task %s failed', self.name)


class SkaledTask(BaseTask):
    NAME = 'skaled'

    def __init__(
        self,
        chain_name: MirageChainName,
        node_config: NodeConfig,
        stream_version: str,
        dutils: Optional[DockerUtils] = None,
    ) -> None:
        self.dutils = dutils
        super().__init__(
            chain_name=chain_name,
            node_config=node_config,
            stream_version=stream_version,
        )

    @property
    def needed(self) -> bool:
        chain_record = ChainRecord(self.chain_name)
        return chain_record.config_version == self.stream_version and (
            not chain_record.sync_config_run or not chain_record.first_run
        )

    def run(self) -> None:
        try:
            run_skaled_pipeline(
                chain_name=cast(MirageChainName, self.chain_name),
                node_config=self.node_config,
                dutils=self.dutils,
            )
        except Exception:
            logger.exception('Task %s failed', self.name)


def start_tasks(
    node_config: NodeConfig,
    dutils: Optional[DockerUtils] = None,
) -> bool:
    logger.info('Starting tasks for node_id: %s', node_config.id)
    stream_version = get_skale_node_version()
    mirage_chain_name = get_mirage_chain_name()

    init_ts, pid = int(time.time()), os.getpid()
    process_report = ProcessReport(mirage_chain_name)
    process_report.update(pid, init_ts)

    tasks = [
        ConfigTask(
            chain_name=mirage_chain_name,
            node_config=node_config,
            stream_version=stream_version,
        ),
        SkaledTask(
            chain_name=mirage_chain_name,
            node_config=node_config,
            stream_version=stream_version,
            dutils=dutils,
        ),
    ]
    execute_tasks(tasks=tasks, process_report=process_report)
    return True
