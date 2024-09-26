import mock
import os
import pathlib
import shutil
import time

import psutil
import pytest

from core.schains.process import ProcessReport, terminate_process
from core.schains.process_manager import run_pm_schain
from tools.configs.schains import SCHAINS_DIR_PATH


@pytest.fixture
def tmp_dir(_schain_name):
    path = os.path.join(SCHAINS_DIR_PATH, _schain_name)
    pathlib.Path(path).mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_run_pm_schain(tmp_dir, skale, skale_ima, node_config, _schain_name):
    def target_regular_mock(*args, **kwargs):
        process_report = args[-1]
        iterations = 5
        for _ in range(iterations):
            process_report.ts = int(time.time())
            time.sleep(1)

    def target_stuck_mock(*args, **kwargs):
        iterations = 10000
        for _ in range(iterations):
            time.sleep(1)

    schain = skale.schains.get_by_name(_schain_name)

    timeout = 7

    with mock.patch('core.schains.process_manager.start_tasks', target_regular_mock):
        run_pm_schain(skale, skale_ima, node_config, schain, timeout=timeout)

    pid = ProcessReport(_schain_name).pid
    assert psutil.Process(pid).is_running()

    start_ts = int(time.time())

    while int(time.time()) - start_ts < 2 * timeout:
        time.sleep(1)
    assert psutil.Process(pid).status() == 'zombie'

    with mock.patch('core.schains.process_manager.start_monitor', target_stuck_mock):
        run_pm_schain(skale, skale_ima, node_config, schain, timeout=timeout)

    pid = ProcessReport(_schain_name).pid

    assert psutil.Process(pid).is_running()

    start_ts = int(time.time())

    while int(time.time()) - start_ts < 2 * timeout:
        try:
            psutil.Process(pid).is_running()
        except psutil.NoSuchProcess:
            break
        with mock.patch('core.schains.process_manager.start_monitor', target_stuck_mock):
            run_pm_schain(skale, skale_ima, node_config, schain, timeout=timeout)
        time.sleep(1)

    with pytest.raises(psutil.NoSuchProcess):
        psutil.Process(pid).is_running()

    pid = ProcessReport(_schain_name).pid
    terminate_process(pid)
