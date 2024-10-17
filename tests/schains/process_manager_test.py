import mock
import logging
import os
import pathlib
import shutil
import time

import psutil
import pytest

from core.schains.process import ProcessReport, terminate_process
from core.schains.process_manager import run_pm_schain
from tools.configs.schains import SCHAINS_DIR_PATH
from tests.utils import get_schain_struct

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 100


@pytest.fixture
def tmp_dir(_schain_name):
    path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def target_regular_mock(*args, **kwargs):
    schain_name = args[1].name
    process_report = ProcessReport(schain_name)
    process_report.update(os.getpid(), int(time.time()))
    logger.info('Starting regular test task runner')
    iterations = 5
    for i in range(iterations):
        process_report.ts = int(time.time())
        logger.info('Regular test task runner beat %s', i)
        time.sleep(1)


def target_stuck_mock(*args, **kwargs):
    schain_name = ProcessReport(args[1].name)
    ProcessReport(schain_name).update(os.getpid(), int(time.time()))
    logger.info('Starting stucked test task runner')
    iterations = 10000
    for i in range(iterations):
        logger.info('Stuck test task runner beat %s', i)
        time.sleep(1)


def wait_for_process_report(process_report):
    wait_it = 0
    while wait_it < MAX_ITERATIONS and not process_report.is_exist():
        time.sleep(0.5)
        wait_it += 1
    assert process_report.is_exist()


def test_run_pm_schain(tmp_dir, skale, skale_ima, node_config, _schain_name):
    schain = get_schain_struct(schain_name=_schain_name)

    timeout = 7

    with mock.patch('core.schains.process_manager.start_tasks', target_regular_mock):
        run_pm_schain(skale, skale_ima, node_config, schain, timeout=timeout)

    process_report = ProcessReport(schain.name)
    wait_for_process_report(process_report)

    pid = process_report.pid

    try:
        assert psutil.Process(pid).is_running()
        start_ts = int(time.time())

        while int(time.time()) - start_ts < 2 * timeout:
            time.sleep(1)
            assert psutil.Process(pid).status() not in ('dead', 'stopped')
    finally:
        pid = ProcessReport(_schain_name).pid
        terminate_process(pid)

    old_pid = pid
    wait_it = 0
    while wait_it < MAX_ITERATIONS and process_report.pid == old_pid:
        time.sleep(0.5)
        wait_it += 1

    with mock.patch('core.schains.process_manager.start_tasks', target_stuck_mock):
        run_pm_schain(skale, skale_ima, node_config, schain, timeout=timeout)

    start_ts = int(time.time())

    while int(time.time()) - start_ts < 2 * timeout:
        try:
            psutil.Process(pid).is_running()
        except psutil.NoSuchProcess:
            break
        time.sleep(1)

    try:
        with pytest.raises(psutil.NoSuchProcess):
            psutil.Process(pid).is_running()
    finally:
        pid = ProcessReport(_schain_name).pid
        terminate_process(pid)
