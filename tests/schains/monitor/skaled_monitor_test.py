import datetime
from unittest import mock

import freezegun
import pytest

from core.schains.checks import CheckRes, SkaledChecks
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
from core.schains.rotation import get_schain_public_key
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
    public_key=None,
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
        ima_linked=True,
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
    ima_data,
    ssl_folder,
    dutils,
    skaled_checks
):
    name = schain_db
    schain = skale.schains.get_by_name(name)
    public_key = get_schain_public_key(skale, name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        ima_data=ima_data,
        node_config=node_config,
        public_key=public_key,
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
        ima_linked=True,
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
        ima_linked=True,
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
        ima_linked=True,
        dutils=dutils
    )


def test_get_skaled_monitor_new_config(
    skaled_am,
    skaled_checks_new_config,
    schain_db,
    skaled_status
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    state = skaled_checks_new_config.get_all()
    state['rotation_id_updated'] = False
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
    ima_data,
    ssl_folder,
    skaled_status,
    skaled_checks,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain = skale.schains.get_by_name(name)
    public_key = get_schain_public_key(skale, name)

    finish_ts = CURRENT_TIMESTAMP + 10
    with mock.patch(
        f'{__name__}.SkaledActionManager.finish_ts',
        new_callable=mock.PropertyMock
    ) as finish_ts_mock:
        skaled_am = SkaledActionManager(
            schain=schain,
            rule_controller=rule_controller,
            ima_data=ima_data,
            node_config=node_config,
            public_key=public_key,
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
    schain_db,
    skaled_status_exit_time_reached,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks_outdated_config.get_all(),
        schain_record,
        skaled_status_exit_time_reached
    )
    assert mon == UpdateConfigSkaledMonitor


def test_get_skaled_monitor_update_config_no_rotation(
    skaled_am,
    skaled_checks_outdated_config,
    schain_db,
    skaled_status,
    new_upstream
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    state = skaled_checks_outdated_config.get_all()
    state['rotation_id_updated'] = True
    mon = get_skaled_monitor(
        skaled_am,
        state,
        schain_record,
        skaled_status
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


def test_regular_skaled_monitor(skaled_am, skaled_checks):
    mon = RegularSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_backup_skaled_monitor(skaled_am, skaled_checks):
    mon = BackupSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_repair_skaled_monitor(skaled_am, skaled_checks):
    mon = RepairSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_new_config_skaled_monitor(skaled_am, skaled_checks):
    mon = NewConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_recreate_skaled_monitor(skaled_am, skaled_checks):
    mon = RecreateSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_after_exit_skaled_monitor(skaled_am, skaled_checks):
    mon = UpdateConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_no_config_monitor(skaled_am, skaled_checks):
    mon = NoConfigSkaledMonitor(skaled_am, skaled_checks)
    mon.run()


def test_new_node_monitor(skaled_am, skaled_checks):
    mon = NewNodeSkaledMonitor(skaled_am, skaled_checks)
    mon.run()
