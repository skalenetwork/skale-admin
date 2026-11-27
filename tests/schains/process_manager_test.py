import logging
import os
import pathlib
import shutil
import time
from unittest import mock

import psutil
import pytest
from skale import SkaleManager
from skale.types.schain import SchainName

from core.manager_cache import ManagerCache
from core.node_config import NodeConfig
from core.schains.process import ProcessReport, cleanup_schains_pids, terminate_process
from core.schains.process_manager import run_pm_schain
from tests.utils import get_schain_struct
from tools.constants.schains import SCHAINS_DIR_PATH

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
    schain_name = args[0].name
    process_report = ProcessReport(schain_name)
    process_report.update(os.getpid(), int(time.time()))
    logger.info('Starting regular test task runner')
    iterations = 5
    for i in range(iterations):
        process_report.ts = int(time.time())
        logger.info('Regular test task runner beat %s', i)
        time.sleep(0.5)


def target_stuck_mock(*args, **kwargs):
    schain_name = SchainName(args[0].name)
    ProcessReport(schain_name).update(os.getpid(), int(time.time()))
    logger.info('Starting stucked test task runner')
    iterations = 10000
    for i in range(iterations):
        logger.info('Stuck test task runner beat %s', i)
        time.sleep(0.5)


def wait_for_process_report(process_report):
    wait_it = 0
    while wait_it < MAX_ITERATIONS and not process_report.exists():
        time.sleep(0.5)
        wait_it += 1
    assert process_report.exists()


def test_run_pm_schain(
    tmp_dir,
    skale: SkaleManager,
    node_config: NodeConfig,
    clear_manager_cache: ManagerCache,
    _schain_name,
):
    schain = get_schain_struct(_test_schain_name=_schain_name)

    timeout = 2

    with mock.patch('core.schains.process_manager.start_tasks', target_regular_mock):
        with mock.patch('core.schains.process_manager.is_node_part_of_chain', return_value=True):
            run_pm_schain(
                skale, node_config, schain, manager_cache=clear_manager_cache, timeout=timeout
            )

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

    with mock.patch('core.schains.process_manager.start_tasks', target_stuck_mock):
        with mock.patch('core.schains.process_manager.is_node_part_of_chain', return_value=True):
            run_pm_schain(
                skale, node_config, schain, manager_cache=clear_manager_cache, timeout=timeout
            )

    wait_it = 0
    while wait_it < MAX_ITERATIONS and process_report.pid == old_pid:
        time.sleep(0.5)
        wait_it += 1

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


def test_cleanup_schains_pids(
    tmp_dir,
    skale: SkaleManager,
    schain_on_contracts: SchainName,
    node_config: NodeConfig,
    manager_cache: ManagerCache,
):
    schain = skale.schains.get_by_name(schain_on_contracts)

    process_report = ProcessReport(schain.name)
    assert not process_report.exists()

    with mock.patch('core.schains.process_manager.start_tasks', target_regular_mock):
        with mock.patch('core.schains.process_manager.is_node_part_of_chain', return_value=True):
            run_pm_schain(skale, node_config, schain=schain, manager_cache=manager_cache)

    wait_for_process_report(process_report)
    assert process_report.exists()
    cleanup_schains_pids()
    assert not process_report.exists()


def test_run_pm_schain_passes_no_web3_objects_to_the_process(node_config: NodeConfig):
    schain = get_schain_struct(_test_schain_name='fork-safety')
    skale = mock.MagicMock()
    skale.node_rotation.is_rotation_active.return_value = False
    with (
        mock.patch('core.schains.process_manager.is_node_part_of_chain', return_value=True),
        mock.patch('core.schains.process_manager.get_schain_process_info', return_value=(None, 0)),
        mock.patch('core.schains.process_manager.FORK_CONTEXT') as fork_context,
    ):
        run_pm_schain(skale, node_config, schain, manager_cache=mock.MagicMock(), timeout=1)
    fork_context.Process.assert_called_once()
    assert fork_context.Process.call_args.kwargs['args'] == (schain, node_config)
