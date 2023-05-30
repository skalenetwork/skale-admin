import pytest

from core.schains.checks import SkaledChecks
from core.schains.monitor.action import SkaledActionManager

from web.models.schain import SChainRecord


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
    finish_ts = skale.node_rotation.get_schain_finish_ts(
      node_id=rotation_data['leaving_node'],
      schain_name=name
    )
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)
    return SkaledActionManager(
        schain=schain,
        rule_controller=rule_controller,
        ima_data=ima_data,
        finish_ts=finish_ts,
        checks=skaled_checks,
        dutils=dutils
    )


def test_skaled_actions(skaled_am, skaled_checks, cleanup_schain_containers):
    try:
        skaled_am.firewall_rules()
        assert skaled_checks.firewall_rules
        skaled_am.volume()
        assert skaled_checks.volume
        skaled_am.skaled_container()
        assert skaled_checks.skaled_container
        skaled_am.ima_container()
        assert skaled_checks.ima_container
    finally:
        skaled_am.cleanup_schain_docker_entity()
