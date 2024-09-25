import functools
import logging
import os
import pathlib
import shutil
import time
from concurrent.futures import Future
from multiprocessing import Process
from typing import Callable

import pytest

from core.schains.firewall.types import IpRange
from core.schains.firewall.utils import get_sync_agent_ranges
from core.schains.monitor.main import Pipeline, run_pipelines
from core.schains.process import ProcessReport, terminate_process
from core.schains.monitor.tasks import execute_tasks, ITask
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.helper import is_node_part_of_chain


@pytest.fixture
def tmp_dir(_schain_name):
    path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sync_ranges(skale):
    skale.sync_manager.grant_sync_manager_role(skale.wallet.address)
    skale.sync_manager.add_ip_range('test1', '127.0.0.1', '127.0.0.2')
    skale.sync_manager.add_ip_range('test2', '127.0.0.5', '127.0.0.7')
    try:
        yield
    finally:
        skale.sync_manager.remove_ip_range('test1')
        skale.sync_manager.remove_ip_range('test2')


def test_get_sync_agent_ranges(skale, sync_ranges):
    ranges = get_sync_agent_ranges(skale)
    assert ranges == [
        IpRange(start_ip='127.0.0.1', end_ip='127.0.0.2'),
        IpRange(start_ip='127.0.0.5', end_ip='127.0.0.7'),
    ]


def test_get_sync_agent_ranges_empty(skale):
    ranges = get_sync_agent_ranges(skale)
    assert ranges == []


def test_is_node_part_of_chain(skale, schain_on_contracts, node_config):
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, node_config.id)
    assert chain_on_node

    chain_on_node = is_node_part_of_chain(skale, 'a', node_config.id)
    assert not chain_on_node

    node_exist_node = 10000
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, node_exist_node)
    assert not chain_on_node


def test_run_pipelines(tmp_dir, _schain_name):
    def simple_pipeline(index: int):
        logging.info('Running simple pipeline %d', index)
        time.sleep(1)
        logging.info('Finishing simple pipeline %d', index)

    def stuck_pipeline(index: int):
        logging.info('Running stuck pipeline %d', index)
        while True:
            logging.info('Stuck pipeline %d beat', index)
            time.sleep(2)

    process_report = ProcessReport(name=_schain_name)

    target = functools.partial(
        run_pipelines,
        pipelines=[
            Pipeline(name='healthy0', job=functools.partial(simple_pipeline, index=0)),
            Pipeline(name='healthy1', job=functools.partial(simple_pipeline, index=1)),
        ],
        process_report=process_report,
        once=True,
        stuck_timeout=5,
        shutdown_interval=10,
    )

    terminated = False
    monitor_process = Process(target=target)
    try:
        monitor_process.start()
        monitor_process.join()
    finally:
        if monitor_process.is_alive():
            terminated = True
        terminate_process(monitor_process.ident)
    assert not terminated

    target = functools.partial(
        run_pipelines,
        pipelines=[
            Pipeline(name='healthy', job=functools.partial(simple_pipeline, index=0)),
            Pipeline(name='stuck', job=functools.partial(stuck_pipeline, index=1)),
        ],
        process_report=process_report,
        stuck_timeout=5,
        shutdown_interval=10,
    )

    monitor_process = Process(target=target)
    terminated = False

    try:
        monitor_process.start()
        monitor_process.join(timeout=50)
    finally:
        if monitor_process.is_alive():
            terminated = True
        terminate_process(monitor_process.ident)

    assert terminated


def test_execute_tasks(tmp_dir, _schain_name):
    def run_stuck_pipeline(index: int) -> None:
        logging.info('Running stuck pipeline %d', index)
        iterations = 7
        for i in range(iterations):
            logging.info('Stuck pipeline %d beat', index)
            time.sleep(1)

    class StuckedTask(ITask):
        def __init__(self, index) -> None:
            self._name = 'stucked-task'
            self.index = index
            self._stuck_timeout = 3
            self._start_ts = 0
            self._future = Future()

        @property
        def name(self) -> str:
            return self._name

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
            print(f'Updating start_ts {self} {value}')
            self._start_ts = value

        @property
        def task_name(self) -> str:
            return self._task_name

        @property
        def stuck_timeout(self) -> int:
            return self._stuck_timeout

        @property
        def needed(self) -> bool:
            return True

        def create_pipeline(self) -> Callable:
            return functools.partial(run_stuck_pipeline, index=self.index)

    class NotNeededTask(StuckedTask):
        def __init__(self, index: int) -> None:
            super().__init__(index=index)
            self._name = 'not-needed-task'

        @property
        def needed(self) -> bool:
            return False

    process_report = ProcessReport(name=_schain_name)
    tasks = [StuckedTask(0), NotNeededTask(1)]
    execute_tasks(
        tasks=tasks,
        process_report=process_report,
        sleep_interval=1
    )

    print(tasks[0], tasks[1])
    assert tasks[0].start_ts == -1
    assert tasks[1].start_ts == 0
