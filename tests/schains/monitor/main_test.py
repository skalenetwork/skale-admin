import os
import mock

import pytest

from core.schains.checks import SChainChecks, CheckRes
from core.schains.config.directory import schain_config_dir
from core.schains.firewall.types import IpRange
from core.schains.monitor.main import (
    run_monitor_for_schain, get_monitor_type, BackupMonitor, RepairMonitor, PostRotationMonitor,
    RotationMonitor, RegularMonitor, ReloadMonitor
)
from core.schains.runner import get_container_info
from core.schains.firewall.utils import get_sync_agent_ranges

from tools.configs.containers import SCHAIN_CONTAINER
from tools.helper import is_node_part_of_chain
from web.models.schain import upsert_schain_record

from tests.schains.monitor.base_monitor_test import BaseTestMonitor, CrashingTestMonitor


class SChainChecksMock(SChainChecks):
    @property
    def skaled_container(self) -> CheckRes:
        return CheckRes(True)


class SChainChecksMockBad(SChainChecks):
    @property
    def skaled_container(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def checks(schain_db, _schain_name, rule_controller, node_config, ima_data):
    schain_record = upsert_schain_record(schain_db)
    return SChainChecksMock(
        _schain_name,
        node_config.id,
        schain_record,
        rule_controller=rule_controller
    )


@pytest.fixture
def bad_checks(schain_db, _schain_name, rule_controller, node_config, ima_data):
    schain_record = upsert_schain_record(schain_db)
    return SChainChecksMockBad(
        _schain_name,
        node_config.id,
        schain_record,
        rule_controller=rule_controller
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


def test_is_backup_mode(schain_db, checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, False, skaled_status) != BackupMonitor
    schain_record.set_new_schain(False)
    with mock.patch('core.schains.monitor.main.BACKUP_RUN', True):
        assert get_monitor_type(schain_record, checks, False, skaled_status) == BackupMonitor


def test_is_repair_mode(schain_db, checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)

    assert get_monitor_type(schain_record, checks, False, skaled_status) != RepairMonitor
    schain_record.set_repair_mode(True)
    assert get_monitor_type(schain_record, checks, False, skaled_status) == RepairMonitor

    schain_record.set_repair_mode(False)
    assert get_monitor_type(schain_record, checks, False, skaled_status) != RepairMonitor


def test_is_repair_mode_skaled_status(schain_db, checks, bad_checks, skaled_status_repair):
    schain_record = upsert_schain_record(schain_db)
    schain_record.set_repair_mode(False)
    assert get_monitor_type(
        schain_record, checks, False, skaled_status_repair) != RepairMonitor
    assert get_monitor_type(
        schain_record, bad_checks, False, skaled_status_repair) == RepairMonitor


def test_not_post_rotation_mode(schain_db, checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, False, skaled_status) != PostRotationMonitor


def test_is_post_rotation_mode(schain_db, checks, skaled_status_exit_time_reached):
    schain_record = upsert_schain_record(schain_db)
    schain_dir_path = schain_config_dir(schain_db)
    os.makedirs(schain_dir_path, exist_ok=True)
    assert get_monitor_type(
        schain_record, checks, False, skaled_status_exit_time_reached) == PostRotationMonitor


def test_is_rotation_mode(schain_db, checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, False, skaled_status) != RotationMonitor
    assert get_monitor_type(schain_record, checks, True, skaled_status) == RotationMonitor


def test_is_regular_mode(schain_db, checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, True, skaled_status) != RegularMonitor
    assert get_monitor_type(schain_record, checks, False, skaled_status) == RegularMonitor


def test_not_is_reload_mode(schain_db, checks, bad_checks, skaled_status):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, False, skaled_status) != ReloadMonitor
    assert get_monitor_type(schain_record, bad_checks, False, skaled_status) != ReloadMonitor


def test_is_reload_mode(schain_db, checks, bad_checks, skaled_status_reload):
    schain_record = upsert_schain_record(schain_db)
    assert get_monitor_type(schain_record, checks, False, skaled_status_reload) != ReloadMonitor
    assert get_monitor_type(schain_record, bad_checks, False, skaled_status_reload) == ReloadMonitor


def test_run_monitor_for_schain(skale, skale_ima, node_config, schain_db):
    with mock.patch('core.schains.monitor.main.RegularMonitor', CrashingTestMonitor), \
            mock.patch('core.schains.monitor.main.is_node_part_of_chain', return_value=True):
        assert not run_monitor_for_schain(
            skale,
            skale_ima,
            node_config,
            {'name': schain_db, 'partOfNode': 0, 'generation': 0},
            once=True
        )
    with mock.patch('core.schains.monitor.main.RegularMonitor', BaseTestMonitor):
        assert run_monitor_for_schain(
            skale,
            skale_ima,
            node_config,
            {'name': schain_db, 'partOfNode': 0, 'generation': 0},
            once=True
        )


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
    print(ranges)
    assert ranges == [
        IpRange(start_ip='127.0.0.1', end_ip='127.0.0.2'),
        IpRange(start_ip='127.0.0.5', end_ip='127.0.0.7')
    ]


def test_get_sync_agent_ranges_empty(skale):
    ranges = get_sync_agent_ranges(skale)
    assert ranges == []


def test_is_node_part_of_chain(skale, schain_on_contracts, node_config):
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, node_config.id)
    assert not chain_on_node

    chain_on_node = is_node_part_of_chain(skale, 'a', node_config.id)
    assert not chain_on_node

    max_node_id = skale.nodes.get_nodes_number()
    chain_on_node = is_node_part_of_chain(skale, schain_on_contracts, max_node_id - 1)
    assert chain_on_node
