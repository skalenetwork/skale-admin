import os
import mock
from time import sleep

import pytest

from core.schains.monitor.main import (
    run_monitor_for_schain, get_monitor_type, BackupMonitor, RepairMonitor, PostRotationMonitor,
    RotationMonitor, RegularMonitor
)
from core.schains.checks import SChainChecks, CheckRes
from core.schains.config.directory import get_schain_rotation_filepath, schain_config_dir
from core.schains.runner import get_container_info

from tools.configs.containers import SCHAIN_CONTAINER
from tools.helper import write_json
from web.models.schain import upsert_schain_record

from tests.schains.monitor.base_monitor_test import BaseTestMonitor, CrashingTestMonitor


class SChainChecksMock(SChainChecks):
    @property
    def exit_code_ok(self) -> CheckRes:
        return CheckRes(True)


class SChainChecksMockBad(SChainChecks):
    @property
    def exit_code_ok(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def checks(schain_db, node_config, ima_data, dutils):
    schain_record = upsert_schain_record(schain_db)
    return SChainChecksMock(
        schain_db,
        node_config.id,
        schain_record
    )


def run_exited_schain_container(dutils, schain_name: str, exit_code: int):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain_name)
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint=f'bash -c "exit {exit_code}"'
    )


def test_is_backup_mode(schain_db, _schain_name, checks, dutils):
    schain_record = upsert_schain_record(_schain_name)
    assert get_monitor_type(schain_record, checks, False, dutils) != BackupMonitor
    schain_record.set_new_schain(False)
    with mock.patch('core.schains.monitor.main.BACKUP_RUN', True):
        assert get_monitor_type(schain_record, checks, False, dutils) == BackupMonitor


def test_is_repair_mode(schain_db, _schain_name, node_config, checks, dutils):
    schain_record = upsert_schain_record(_schain_name)

    assert get_monitor_type(schain_record, checks, False, dutils) != RepairMonitor
    schain_record.set_repair_mode(True)
    assert get_monitor_type(schain_record, checks, False, dutils) == RepairMonitor

    schain_record.set_repair_mode(False)
    assert get_monitor_type(schain_record, checks, False, dutils) != RepairMonitor
    bad_checks = SChainChecksMockBad(
        schain_db,
        node_config.id,
        schain_record
    )
    assert get_monitor_type(schain_record, bad_checks, False, dutils) == RepairMonitor


def test_is_repair_mode_state_root(schain_db, _schain_name, node_config, dutils):
    schain_record = upsert_schain_record(_schain_name)
    checks = SChainChecks(
        schain_db,
        node_config.id,
        schain_record,
        dutils=dutils
    )
    assert get_monitor_type(schain_record, checks, False, dutils) != RepairMonitor
    run_exited_schain_container(dutils, _schain_name, 200)
    sleep(10)
    assert get_monitor_type(schain_record, checks, False, dutils) == RepairMonitor


def test_is_post_rotation_mode(schain_db, _schain_name, dutils, checks):
    schain_record = upsert_schain_record(_schain_name)
    assert get_monitor_type(schain_record, checks, False, dutils) != PostRotationMonitor
    schain_dir_path = schain_config_dir(_schain_name)
    os.makedirs(schain_dir_path, exist_ok=True)
    schain_rotation_filepath = get_schain_rotation_filepath(_schain_name)
    write_json(schain_rotation_filepath, {'heh': 'haha'})
    run_exited_schain_container(dutils, _schain_name, 0)
    sleep(10)
    assert get_monitor_type(schain_record, checks, False, dutils) == PostRotationMonitor


def test_is_rotation_mode(schain_db, _schain_name, dutils, checks):
    schain_record = upsert_schain_record(_schain_name)
    assert get_monitor_type(schain_record, checks, False, dutils) != RotationMonitor
    assert get_monitor_type(schain_record, checks, True, dutils) == RotationMonitor


def test_is_regular_mode(schain_db, _schain_name, dutils, checks):
    schain_record = upsert_schain_record(_schain_name)
    assert get_monitor_type(schain_record, checks, True, dutils) != RegularMonitor
    assert get_monitor_type(schain_record, checks, False, dutils) == RegularMonitor


def test_run_monitor_for_schain(skale, skale_ima, node_config, schain_db, dutils):
    with mock.patch('core.schains.monitor.main.RegularMonitor', CrashingTestMonitor):
        assert not run_monitor_for_schain(
            skale, skale_ima, node_config, {'name': schain_db, 'partOfNode': 0}, dutils, once=True)
    with mock.patch('core.schains.monitor.main.RegularMonitor', BaseTestMonitor):
        assert run_monitor_for_schain(
            skale, skale_ima, node_config, {'name': schain_db, 'partOfNode': 0}, dutils, once=True)