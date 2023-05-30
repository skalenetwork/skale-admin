import pytest

from core.schains.checks import ContainerChecks
from core.schains.monitor.action import ContainerActionManager

from web.models.schain import SChainRecord


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def container_checks(
    schain_db,
    skale,
    rule_controller,
    dutils
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return ContainerChecks(
        schain_name=name,
        schain_record=schain_record,
        rule_controller=rule_controller,
        ima_linked=True,
        dutils=dutils
    )


@pytest.fixture
def container_am(
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
    container_checks
):
    name = schain_db
    finish_ts = skale.node_rotation.get_schain_finish_ts(
      node_id=rotation_data['leaving_node'],
      schain_name=name
    )
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)
    return ContainerActionManager(
        schain=schain,
        rule_controller=rule_controller,
        ima_data=ima_data,
        finish_ts=finish_ts,
        checks=container_checks,
        dutils=dutils
    )


def test_container_actions(container_am, container_checks):
    container_am.firewall_rules()
    container_am.volume()
    container_am.skaled_container()
    container_am.ima_container()
