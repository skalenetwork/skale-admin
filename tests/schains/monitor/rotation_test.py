import pytest

from core.schains.monitor.rotation_monitor import RotationMonitor
from core.schains.checks import SChainChecks

from web.models.schain import SChainRecord

from tests.utils import get_test_rc


DEFAULT_ROTATION_DATA = {
    'rotation_id': 1,
    'finish_ts': 12345678,
    'new_node': 2999,
    'leaving_node': 1999
}


@pytest.fixture
def new_checks(schain_db, node_config, ima_data, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    return SChainChecks(
        schain_db,
        node_config.id,
        schain_record=schain_record,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )


def get_rotation_monitor(skale, ima_data, node_config, schain_db, dutils, new_checks,
                         rotation_data, rule_controller_creator):
    return RotationMonitor(
        skale=skale,
        ima_data=ima_data,
        schain={'name': schain_db, 'partOfNode': 0},
        node_config=node_config,
        rotation_data=rotation_data,
        checks=new_checks,
        rule_controller_creator=rule_controller_creator,
        dutils=dutils
    )


def test_is_new_node_no_config(
    node_config,
    skale,
    ima_data,
    schain_db,
    dutils,
    new_checks
):
    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=DEFAULT_ROTATION_DATA,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() == test_monitor.new_node


def test_is_new_node(node_config, schain_config, skale, ima_data, schain_db, dutils, new_checks):
    rotation_data_new_node = {
        'rotation_id': 1,
        'finish_ts': 12345678,
        'new_node': node_config.id,
        'leaving_node': 1999
    }
    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=rotation_data_new_node,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() == test_monitor.new_node

    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=DEFAULT_ROTATION_DATA,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() != test_monitor.new_node


def test_is_leaving_node(
    node_config,
    schain_config,
    skale,
    ima_data,
    schain_db,
    dutils,
    new_checks
):
    rotation_data_leaving_node = {
        'rotation_id': 1,
        'finish_ts': 12345678,
        'new_node': 9999,
        'leaving_node': node_config.id,
    }
    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=rotation_data_leaving_node,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() == test_monitor.leaving_node

    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=DEFAULT_ROTATION_DATA,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() != test_monitor.leaving_node


def test_is_staying_node(
    node_config,
    skale,
    schain_config,
    ima_data,
    schain_db,
    dutils,
    new_checks
):
    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=DEFAULT_ROTATION_DATA,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    assert test_monitor.get_rotation_mode_func() == test_monitor.staying_node


@pytest.mark.skip(reason="test should be improved")
def test_rotation_request(
    node_config,
    skale,
    schain_config,
    ima_data,
    schain_db,
    dutils,
    new_checks
):
    rotation_data_leaving_node = {
        'rotation_id': 1,
        'finish_ts': 12345678,
        'new_node': 9999,
        'leaving_node': node_config.id,
    }
    test_monitor = get_rotation_monitor(
        skale=skale,
        ima_data=ima_data,
        schain_db=schain_db,
        node_config=node_config,
        rotation_data=rotation_data_leaving_node,
        new_checks=new_checks,
        rule_controller_creator=get_test_rc,
        dutils=dutils
    )
    test_monitor.rotation_request()
