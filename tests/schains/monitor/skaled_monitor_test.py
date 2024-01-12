import datetime
import os
import time
from unittest import mock

import freezegun
import pytest

from core.schains.checks import CheckRes, SkaledChecks
from core.schains.config.directory import schain_config_dir
from core.schains.monitor.action import SkaledActionManager
from core.schains.monitor.skaled_monitor import (
    BackupSkaledMonitor,
    get_skaled_monitor,
    NewConfigSkaledMonitor,
    NewNodeSkaledMonitor,
    NoConfigSkaledMonitor,
    RecreateSkaledMonitor,
    RegularSkaledMonitor,
    RepairSkaledMonitor,
    UpdateConfigSkaledMonitor
)
from core.schains.exit_scheduler import ExitScheduleFileManager
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from web.models.schain import SChainRecord


CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


def run_ima_container_mock(schain: dict, mainnet_chain_id: int, dutils=None):
    image_name, container_name, _, _ = get_container_info(
        IMA_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


def monitor_schain_container_mock(
    schain,
    schain_record,
    skaled_status,
    download_snapshot=False,
    start_ts=None,
    dutils=None
):
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, schain['name'])
    dutils.safe_rm(container_name)
    dutils.run_container(
        image_name=image_name,
        name=container_name,
        entrypoint='bash -c "while true; do foo; sleep 2; done"'
    )


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def skaled_checks(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecks(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )


@pytest.fixture
def skaled_am(
    schain_db,
    skale,
    node_config,
    rule_controller,
    schain_on_contracts,
    predeployed_ima,
    rotation_data,
    secret_key,
    ssl_folder,
    dutils,
    skaled_checks
):
    name = schain_db
    schain = skale.schains.get_by_name(name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        node_config=node_config,
        checks=skaled_checks,
        dutils=dutils
    )


class SkaledChecksNoConfig(SkaledChecks):
    @property
    def config(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def skaled_checks_no_config(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksNoConfig(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )


class SkaledChecksConfigOutdated(SkaledChecks):
    @property
    def config_updated(self) -> CheckRes:
        return CheckRes(False)

    @property
    def rotation_id_updated(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def skaled_checks_outdated_config(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksConfigOutdated(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )


def test_get_skaled_monitor_no_config(skaled_am, skaled_checks_no_config, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks_no_config.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == NoConfigSkaledMonitor


def test_get_skaled_monitor_regular_and_backup(skaled_am, skaled_checks, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == RegularSkaledMonitor

    schain_record.set_backup_run(True)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == RegularSkaledMonitor

    schain_record.set_first_run(False)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == RegularSkaledMonitor

    schain_record.set_new_schain(False)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == BackupSkaledMonitor


def test_get_skaled_monitor_repair(skaled_am, skaled_checks, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain_record.set_repair_mode(True)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == RepairSkaledMonitor


def test_get_skaled_monitor_repair_skaled_status(
    skaled_am,
    skaled_checks,
    schain_db,
    skaled_status_repair
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status_repair
    )
    assert mon == RepairSkaledMonitor

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status_repair,
        automatic_repair=False
    )
    assert mon == RegularSkaledMonitor


class SkaledChecksWithConfig(SkaledChecks):
    @property
    def config_updated(self) -> CheckRes:
        return CheckRes(False)

    @property
    def config(self) -> CheckRes:
        return CheckRes(True)

    @property
    def rotation_id_updated(self) -> CheckRes:
        return CheckRes(True)

    @property
    def skaled_container(self) -> CheckRes:
        return CheckRes(True)

    @property
    def container(self) -> CheckRes:
        return CheckRes(True)


@pytest.fixture
def skaled_checks_new_config(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksWithConfig(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_skaled_monitor_new_config(
    skale,
    skaled_am,
    skaled_checks_new_config,
    schain_db,
    skaled_status,
    node_config,
    rule_controller,
    schain_on_contracts,
    predeployed_ima,
    rotation_data,
    secret_keys,
    ssl_folder,
    skaled_checks,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    state = skaled_checks_new_config.get_all()
    state['rotation_id_updated'] = False

    schain = skale.schains.get_by_name(name)

    with mock.patch(
        f'{__name__}.SkaledActionManager.upstream_finish_ts',
        new_callable=mock.PropertyMock
    ) as finish_ts_mock:
        finish_ts_mock.return_value = CURRENT_TIMESTAMP - 10
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            checks=skaled_checks,
            dutils=dutils
        )
        mon = get_skaled_monitor(
            skaled_am,
            state,
            schain_record,
            skaled_status
        )
        assert mon == RegularSkaledMonitor
        finish_ts_mock.return_value = CURRENT_TIMESTAMP + 10
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            checks=skaled_checks,
            dutils=dutils
        )
        mon = get_skaled_monitor(
            skaled_am,
            state,
            schain_record,
            skaled_status
        )
        assert mon == NewConfigSkaledMonitor


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_skaled_monitor_new_node(
    schain_db,
    skale,
    node_config,
    rule_controller,
    schain_on_contracts,
    predeployed_ima,
    rotation_data,
    secret_key,
    ssl_folder,
    skaled_status,
    skaled_checks,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain = skale.schains.get_by_name(name)

    finish_ts = CURRENT_TIMESTAMP + 10
    with mock.patch(
        f'{__name__}.SkaledActionManager.finish_ts',
        new_callable=mock.PropertyMock
    ) as finish_ts_mock:
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            checks=skaled_checks,
            dutils=dutils
        )
        finish_ts_mock.return_value = finish_ts

        mon = get_skaled_monitor(
            skaled_am,
            skaled_checks.get_all(),
            schain_record,
            skaled_status
        )
        assert mon == NewNodeSkaledMonitor


def test_get_skaled_monitor_update_config(
    skaled_am,
    skaled_checks_outdated_config,
    skaled_checks_new_config,
    schain_db,
    skaled_status_exit_time_reached,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    status = skaled_checks_outdated_config.get_all()
    status['skaled_container'] = False

    mon = get_skaled_monitor(
        skaled_am,
        status,
        schain_record,
        skaled_status_exit_time_reached
    )
    assert mon == UpdateConfigSkaledMonitor

    status = skaled_checks_new_config.get_all()
    status['skaled_container'] = False
    mon = get_skaled_monitor(
        skaled_am,
        status,
        schain_record,
        skaled_status_exit_time_reached
    )
    assert mon == UpdateConfigSkaledMonitor


def test_get_skaled_monitor_recreate(
    skaled_am,
    skaled_checks,
    schain_db,
    skaled_status
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    schain_record.set_needs_reload(True)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status
    )
    assert mon == RecreateSkaledMonitor


def test_regular_skaled_monitor(
    skaled_am,
    skaled_checks,
    clean_docker,
    dutils
):
    mon = RegularSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rc.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    assert dutils.safe_get_container(f'skale_schain_{skaled_am.name}')
    assert dutils.safe_get_container(f'skale_ima_{skaled_am.name}')


def test_backup_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = BackupSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rc.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    schain_container = dutils.safe_get_container(
        f'skale_schain_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
    assert dutils.safe_get_container(f'skale_ima_{skaled_am.name}')


def test_repair_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = RepairSkaledMonitor(skaled_am, skaled_checks)
    ts_before = time.time()
    mon.run()
    time.sleep(1)
    assert skaled_am.rc.is_rules_synced
    assert dutils.get_vol(skaled_am.name)

    assert dutils.get_vol_created_ts(skaled_am.name) > ts_before
    schain_container = dutils.safe_get_container(
        f'skale_schain_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
    assert dutils.get_container_created_ts(schain_container.id) > ts_before
    assert not dutils.safe_get_container(f'skale_ima_{skaled_am.name}')


def test_new_config_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NewConfigSkaledMonitor(skaled_am, skaled_checks)
    ts = time.time()
    esfm = ExitScheduleFileManager(mon.am.name)
    with mock.patch('core.schains.monitor.action.get_finish_ts_from_latest_upstream',
                    return_value=ts):
        mon.run()
        assert esfm.exit_ts == ts
    assert skaled_am.rc.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    assert dutils.safe_get_container(f'skale_schain_{skaled_am.name}')
    assert dutils.safe_get_container(f'skale_ima_{skaled_am.name}')


@pytest.mark.skip
def test_new_config_skaled_monitor_failed_skaled(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NewConfigSkaledMonitor(skaled_am, skaled_checks)
    with mock.patch('core.schains.monitor.containers.run_schain_container') \
            as run_skaled_container_mock:
        mon.run()
        assert skaled_am.rc.is_rules_synced
        assert run_skaled_container_mock.assert_not_called()


def test_recreate_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = RecreateSkaledMonitor(skaled_am, skaled_checks)
    ts_before = time.time()
    time.sleep(1)
    mon.run()
    schain_container = dutils.safe_get_container(
        f'skale_schain_{skaled_am.name}')
    assert schain_container
    assert dutils.get_container_created_ts(schain_container.id) > ts_before


def test_update_config_skaled_monitor(
    skaled_am,
    skaled_checks,
    dutils,
    clean_docker,
    upstreams,
    skaled_status_exit_time_reached
):
    name = skaled_checks.name
    ts_before = time.time()
    time.sleep(1)
    mon = UpdateConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert dutils.get_vol(name)
    assert dutils.get_vol_created_ts(name) > ts_before
    schain_container = dutils.safe_get_container(
        f'skale_schain_{name}'
    )
    assert schain_container
    assert dutils.get_container_created_ts(schain_container.id) > ts_before
    os.stat(os.path.join(schain_config_dir(name),
            f'schain_{name}.json')).st_mtime > ts_before


def test_no_config_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NoConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert not dutils.get_vol(skaled_am.name)
    assert not dutils.safe_get_container(f'skale_schain_{skaled_am.name}')
    assert not dutils.safe_get_container(f'skale_ima_{skaled_am.name}')


def test_new_node_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NewNodeSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rc.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    schain_container = dutils.safe_get_container(
        f'skale_schain_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
