import datetime

import pytest

from core.schains.checks import CheckRes, SkaledChecks
from core.schains.monitor.action import SkaledActionManager
from core.schains.monitor.skaled_monitor import (
    BackupSkaledMonitor,
    get_skaled_monitor,
    NewConfigSkaledMonitor,
    NewNodeMonitor,
    NoConfigMonitor,
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


def test_get_skaled_monitor_no_config(skaled_am, skaled_checks_no_config, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks_no_config,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, NoConfigMonitor)


def test_get_skaled_monitor_regular_and_backup(skaled_am, skaled_checks, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, RegularSkaledMonitor)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status,
        backup_run=True
    )
    assert isinstance(mon, RegularSkaledMonitor)

    schain_record.set_new_schain(False)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status,
        backup_run=True
    )
    assert isinstance(mon, BackupSkaledMonitor)

    schain_record.set_new_schain(False)
    schain_record.set_first_run(False)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status,
        backup_run=True
    )
    assert isinstance(mon, RegularSkaledMonitor)


def test_get_skaled_monitor_repair(skaled_am, skaled_checks, skaled_status, schain_db):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    schain_record.set_repair_mode(True)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, RepairSkaledMonitor)


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
        skaled_checks,
        schain_record,
        skaled_status_repair
    )
    assert isinstance(mon, RepairSkaledMonitor)


class SkaledChecksWithConfig(SkaledChecks):
    @property
    def config_updated(self) -> CheckRes:
        return CheckRes(False)

    @property
    def config(self) -> CheckRes:
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

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks_new_config,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, NewConfigSkaledMonitor)


def test_get_skaled_monitor_update_config(
    skaled_am,
    skaled_checks,
    schain_db,
    skaled_status_exit_time_reached,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)

    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status_exit_time_reached
    )
    assert isinstance(mon, UpdateConfigSkaledMonitor)


def test_get_skaled_monitor_update_config_no_rotation(
    skaled_am,
    skaled_checks,
    schain_db,
    skaled_status,
    new_upstream
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    mon = get_skaled_monitor(
        skaled_am,
        skaled_checks,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, UpdateConfigSkaledMonitor)


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
        skaled_checks,
        schain_record,
        skaled_status
    )
    assert isinstance(mon, RecreateSkaledMonitor)


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
    mon = NoConfigMonitor(skaled_am, skaled_checks)
    mon.run()


def test_new_node_monitor(skaled_am, skaled_checks):
    mon = NewNodeMonitor(skaled_am, skaled_checks)
    mon.run()
