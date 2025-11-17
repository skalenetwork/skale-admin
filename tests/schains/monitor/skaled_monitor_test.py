import datetime
import os
import time
from unittest import mock

import freezegun
import pytest

from core.checks.schain import CheckRes, SkaledChecks
from core.config.schain.directory import schain_config_dir
from core.monitor.schain.action_skaled import SkaledActionManager
from core.monitor.schain.monitor_skaled import (
    BackupSkaledMonitor,
    NewNodeSkaledMonitor,
    NoConfigSkaledMonitor,
    RecreateSkaledMonitor,
    RegularSkaledMonitor,
    ReloadGroupSkaledMonitor,
    ReloadIpSkaledMonitor,
    RepairSkaledMonitor,
    UpdateConfigSkaledMonitor,
    get_skaled_monitor,
)
from core.schains.exit_scheduler import ExitScheduleFileManager
from core.schains.external_config import ExternalConfig
from tests.utils import CURRENT_TS
from web.models.schain import SChainRecord

CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def skaled_checks(schain_db, skale, rule_controller, dutils):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecks(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils,
        passive_node=False,
    )


@pytest.fixture
def skaled_am(
    schain_db,
    skale,
    node_config,
    rule_controller,
    schain_on_contracts,
    rotation_data,
    secret_key,
    ssl_folder,
    ima_migration_schedule,
    ncli_status,
    dutils,
    skaled_checks,
):
    name = schain_db
    schain = skale.schains.get_by_name(name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        node_config=node_config,
        ncli_status=ncli_status,
        checks=skaled_checks,
        dutils=dutils,
    )


class SkaledChecksNoConfig(SkaledChecks):
    @property
    def config(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def skaled_checks_no_config(schain_db, skale, rule_controller, dutils):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksNoConfig(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils,
    )


class SkaledChecksConfigOutdated(SkaledChecks):
    @property
    def config_updated(self) -> CheckRes:
        return CheckRes(False)

    @property
    def rotation_id_updated(self) -> CheckRes:
        return CheckRes(False)


@pytest.fixture
def skaled_checks_outdated_config(schain_db, skale, rule_controller, dutils):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksConfigOutdated(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils,
    )


def test_get_skaled_monitor_no_config(
    skaled_am, skaled_checks_no_config, skaled_status, schain_db, ncli_status
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am, skaled_checks_no_config.get_all(), schain_record, skaled_status, ncli_status
    )
    assert mon == NoConfigSkaledMonitor


def test_get_skaled_monitor_regular_and_backup(
    skaled_am, skaled_checks, skaled_status, schain_db, ncli_status
):
    name = schain_db
    schain_record: SChainRecord = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am, skaled_checks.get_all(), schain_record, skaled_status, ncli_status
    )
    assert mon == RegularSkaledMonitor

    schain_record.set_backup_run(True)
    mon = get_skaled_monitor(
        skaled_am, skaled_checks.get_all(), schain_record, skaled_status, ncli_status
    )
    assert mon == BackupSkaledMonitor

    schain_record.set_backup_run(False)
    mon = get_skaled_monitor(
        skaled_am, skaled_checks.get_all(), schain_record, skaled_status, ncli_status
    )
    assert mon == RegularSkaledMonitor


def test_get_skaled_monitor_repair(skaled_am, skaled_checks, skaled_status, schain_db, ncli_status):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain_record.set_repair_date(datetime.datetime.utcfromtimestamp(CURRENT_TS - 10))

    mon = get_skaled_monitor(
        skaled_am, skaled_checks.get_all(), schain_record, skaled_status, ncli_status
    )
    assert mon == RepairSkaledMonitor


def test_get_skaled_monitor_repair_skaled_status(
    skaled_am, skaled_checks, schain_db, skaled_status_repair, ncli_status
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    mon = get_skaled_monitor(
        skaled_am, skaled_checks.get_all(), schain_record, skaled_status_repair, ncli_status
    )
    assert mon == RepairSkaledMonitor

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks.get_all(),
        schain_record,
        skaled_status_repair,
        ncli_status,
        automatic_repair=False,
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
def skaled_checks_new_config(schain_db, skale, rule_controller, dutils):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return SkaledChecksWithConfig(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils,
    )


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_skaled_monitor_reload_group(
    skale,
    skaled_am,
    skaled_checks_new_config,
    schain_db,
    skaled_status,
    node_config,
    rule_controller,
    schain_on_contracts,
    rotation_data,
    secret_keys,
    ssl_folder,
    skaled_checks,
    ncli_status,
    dutils,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    state = skaled_checks_new_config.get_all()
    state['rotation_id_updated'] = False

    schain = skale.schains.get_by_name(name)

    with mock.patch(
        f'{__name__}.SkaledActionManager.upstream_finish_ts', new_callable=mock.PropertyMock
    ) as finish_ts_mock:
        finish_ts_mock.return_value = CURRENT_TIMESTAMP - 10
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            checks=skaled_checks,
            ncli_status=ncli_status,
            dutils=dutils,
        )
        mon = get_skaled_monitor(skaled_am, state, schain_record, skaled_status, ncli_status)
        assert mon == RegularSkaledMonitor
        finish_ts_mock.return_value = CURRENT_TIMESTAMP + 10
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            checks=skaled_checks,
            ncli_status=ncli_status,
            dutils=dutils,
        )
        mon = get_skaled_monitor(skaled_am, state, schain_record, skaled_status, ncli_status)
        assert mon == ReloadGroupSkaledMonitor


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_skaled_monitor_reload_ip(
    skale,
    skaled_am,
    skaled_checks_new_config,
    schain_db,
    skaled_status,
    node_config,
    rule_controller,
    schain_on_contracts,
    rotation_data,
    secret_keys,
    ssl_folder,
    skaled_checks,
    ncli_status,
    dutils,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    state = skaled_checks_new_config.get_all()
    state['rotation_id_updated'] = False

    schain = skale.schains.get_by_name(name)

    econfig = ExternalConfig(name)

    skaled_am = SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        node_config=node_config,
        checks=skaled_checks,
        ncli_status=ncli_status,
        dutils=dutils,
    )
    mon = get_skaled_monitor(skaled_am, state, schain_record, skaled_status, ncli_status)
    assert mon == RegularSkaledMonitor

    estate = econfig.read()
    estate['reload_ts'] = CURRENT_TIMESTAMP + 10
    econfig.write(estate)

    mon = get_skaled_monitor(skaled_am, state, schain_record, skaled_status, ncli_status)
    assert mon == ReloadIpSkaledMonitor


@freezegun.freeze_time(CURRENT_DATETIME)
def test_get_skaled_monitor_new_node(
    schain_db,
    skale,
    node_config,
    rule_controller,
    schain_on_contracts,
    rotation_data,
    secret_key,
    ssl_folder,
    skaled_status,
    skaled_checks,
    ima_migration_schedule,
    ncli_status,
    dutils,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain = skale.schains.get_by_name(name)

    finish_ts = CURRENT_TIMESTAMP + 10
    with mock.patch(
        f'{__name__}.SkaledActionManager.finish_ts', new_callable=mock.PropertyMock
    ) as finish_ts_mock:
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            node_config=node_config,
            ncli_status=ncli_status,
            checks=skaled_checks,
            dutils=dutils,
        )
        finish_ts_mock.return_value = finish_ts

        mon = get_skaled_monitor(
            skaled_am, skaled_checks.get_all(), schain_record, skaled_status, ncli_status
        )
        assert mon == NewNodeSkaledMonitor


def test_get_skaled_monitor_update_config(
    skaled_am,
    skaled_checks_outdated_config,
    skaled_checks_new_config,
    schain_db,
    skaled_status_exit_time_reached,
    ncli_status,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    status = skaled_checks_outdated_config.get_all()
    status['skaled_container'] = False

    mon = get_skaled_monitor(
        skaled_am, status, schain_record, skaled_status_exit_time_reached, ncli_status
    )
    assert mon == UpdateConfigSkaledMonitor

    status = skaled_checks_new_config.get_all()
    status['skaled_container'] = False
    mon = get_skaled_monitor(
        skaled_am, status, schain_record, skaled_status_exit_time_reached, ncli_status
    )
    assert mon == UpdateConfigSkaledMonitor


def test_get_skaled_monitor_recreate(
    skaled_am, skaled_checks, schain_db, skaled_status, ncli_status
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain_record.set_ssl_change_date(datetime.datetime.now())
    status = skaled_checks.get_all()

    with mock.patch(
        'core.chain.ssl.get_ssl_files_change_date', return_value=datetime.datetime.now()
    ):
        status['skaled_container'] = False
        mon = get_skaled_monitor(skaled_am, status, schain_record, skaled_status, ncli_status)
        assert mon == RegularSkaledMonitor
        status['skaled_container'] = True
        mon = get_skaled_monitor(skaled_am, status, schain_record, skaled_status, ncli_status)
        assert mon == RecreateSkaledMonitor


def test_regular_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = RegularSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rule_controller.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    assert dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert dutils.safe_get_container(f'sk_ima_{skaled_am.name}')


def test_backup_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = BackupSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rule_controller.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    schain_container = dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
    assert dutils.safe_get_container(f'sk_ima_{skaled_am.name}')


def test_repair_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = RepairSkaledMonitor(skaled_am, skaled_checks)
    ts_before = time.time()
    mon.run()
    time.sleep(1)
    assert skaled_am.rule_controller.is_rules_synced
    assert dutils.get_vol(skaled_am.name)

    assert dutils.get_vol_created_ts(skaled_am.name) > ts_before
    schain_container = dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
    assert dutils.get_container_created_ts(schain_container.id) > ts_before
    assert not dutils.safe_get_container(f'sk_ima_{skaled_am.name}')


def test_group_reload_skaled_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = ReloadGroupSkaledMonitor(skaled_am, skaled_checks)
    ts = time.time()
    esfm = ExitScheduleFileManager(mon.am.name)
    with mock.patch(
        'core.monitor.schain.action_skaled.get_finish_ts_from_latest_upstream', return_value=ts
    ):
        mon.run()
        assert esfm.exit_ts == ts
    assert skaled_am.rule_controller.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    assert dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert dutils.safe_get_container(f'sk_ima_{skaled_am.name}')


@pytest.mark.skip
def test_group_reload_skaled_monitor_failed_skaled(skaled_am, skaled_checks, clean_docker, dutils):
    mon = ReloadGroupSkaledMonitor(skaled_am, skaled_checks)
    with mock.patch('core.chain.containers.run_skaled_container') as run_skaled_container_mock:
        mon.run()
        assert skaled_am.rule_controller.is_rules_synced
        assert run_skaled_container_mock.assert_not_called()


def test_recreate_skaled_monitor(
    skaled_am: SkaledActionManager, skaled_checks, clean_docker, dutils
):
    mon = RecreateSkaledMonitor(skaled_am, skaled_checks)
    ts_before = time.time()
    time.sleep(1)
    mon.run()
    schain_container = dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert schain_container
    assert dutils.get_container_created_ts(schain_container.id) > ts_before


def test_update_config_skaled_monitor(
    skaled_am,
    skaled_checks: SkaledChecks,
    dutils,
    clean_docker,
    upstreams,
    skaled_status_exit_time_reached,
    remove_schain_config_file,
):
    name = skaled_checks.name
    ts_before = time.time()
    time.sleep(1)
    mon = UpdateConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert dutils.get_vol(name)
    assert dutils.get_vol_created_ts(name) > ts_before
    schain_container = dutils.safe_get_container(f'sk_skaled_{name}')
    assert schain_container
    assert dutils.get_container_created_ts(schain_container.id) > ts_before
    assert (
        os.stat(os.path.join(schain_config_dir(name), f'schain_{name}.json')).st_mtime > ts_before
    )


def test_no_config_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NoConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert not dutils.get_vol(skaled_am.name)
    assert not dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert not dutils.safe_get_container(f'sk_ima_{skaled_am.name}')


def test_new_node_monitor(skaled_am, skaled_checks, clean_docker, dutils):
    mon = NewNodeSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
    assert skaled_am.rule_controller.is_rules_synced
    assert dutils.get_vol(skaled_am.name)
    schain_container = dutils.safe_get_container(f'sk_skaled_{skaled_am.name}')
    assert schain_container
    assert '--download-snapshot' in dutils.get_cmd(schain_container.id)
