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

import abc
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Sequence

from core.node_config import NodeConfig
from core.schains.process import ProcessReport
from core.types.chain import ChainName

logger = logging.getLogger(__name__)


SLEEP_INTERVAL_SECONDS = 10


class ITask(metaclass=abc.ABCMeta):
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def stuck_timeout(self) -> int:
        pass

    @abc.abstractmethod
    def run(self) -> None:
        pass

    @property
    @abc.abstractmethod
    def future(self) -> Future:
        pass

    @future.setter
    @abc.abstractmethod
    def future(self, value: Future) -> None:
        pass

    @property
    @abc.abstractmethod
    def needed(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def start_ts(self) -> int:
        pass

    @start_ts.setter
    @abc.abstractmethod
    def start_ts(self, value: int) -> None:
        pass


class BaseTask(ITask):
    NAME = ''
    STUCK_TIMEOUT_SECONDS = 60 * 60 * 2

    def __init__(
        self,
        chain_name: ChainName,
        node_config: NodeConfig,
        stream_version: str,
    ) -> None:
        self.chain_name = chain_name
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
    def start_ts(self) -> int:
        return self._start_ts

    @start_ts.setter
    def start_ts(self, value: int) -> None:
        self._start_ts = value

    @property
    def stuck_timeout(self) -> int:
        return self.STUCK_TIMEOUT_SECONDS


def execute_tasks(
    tasks: Sequence[ITask],
    process_report: ProcessReport,
    sleep_interval: int = SLEEP_INTERVAL_SECONDS,
) -> None:
    logger.info('Running tasks %s', tasks)
    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix='T') as executor:
        stuck = []
        while True:
            for _, task in enumerate(tasks):
                logger.info(
                    'Status of %s, running: %s needed: %s stuck: %s',
                    task.name,
                    task.future.running(),
                    task.needed,
                    len(stuck),
                )
                if not task.future.running() and task.needed and len(stuck) == 0:
                    if task.future.done():
                        logger.info('Done')
                        logger.info('Result %s', task.future.result())
                    task.start_ts = int(time.time())
                    logger.info('Starting task %s at %d', task.name, task.start_ts)
                    task.future = executor.submit(task.run)
                elif task.future.running():
                    if int(time.time()) - task.start_ts > task.stuck_timeout:
                        logger.info('Canceling future for %s', task.name)
                        canceled = task.future.cancel()
                        if not canceled:
                            logger.warning('Stuck detected for job %s', task.name)
                            task.start_ts = -1
                            stuck.append(task.name)
            time.sleep(sleep_interval)
            if len(stuck) > 0:
                logger.info('Sleeping before subverting execution')
                executor.shutdown(wait=False)
                logger.info('Subverting execution. Stuck %s', stuck)
                process_report.ts = 0
                break
            process_report.ts = int(time.time())
