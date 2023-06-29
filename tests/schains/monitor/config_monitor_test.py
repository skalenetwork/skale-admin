import os

import pytest

from core.schains.checks import ConfigChecks
from core.schains.config.directory import new_schain_config_filepath

from core.schains.monitor.action import ConfigActionManager
from core.schains.monitor.config_monitor import RegularConfigMonitor

from web.models.schain import SChainRecord

from tests.utils import CONFIG_STREAM


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def config_checks(
    schain_db,
    skale,
    node_config,
    schain_on_contracts,
    rotation_data,
    estate
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        rotation_id=rotation_data['rotation_id'],
        stream_version=CONFIG_STREAM,
        estate=estate
    )


@pytest.fixture
def config_am(
    schain_db,
    skale,
    node_config,
    schain_on_contracts,
    predeployed_ima,
    secret_key,
    config_checks,
    estate
):
    name = schain_db
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)

    am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=CONFIG_STREAM,
        checks=config_checks,
        estate=estate
    )
    am.dkg = lambda s: True
    return am


@pytest.fixture
def regular_config_monitor(config_am, config_checks):
    return RegularConfigMonitor(
        action_manager=config_am,
        checks=config_checks
    )


def test_regular_config_monitor(schain_db, regular_config_monitor, rotation_data):
    name = schain_db
    rotation_id = rotation_data['rotation_id']
    regular_config_monitor.run()
    assert os.path.isfile(new_schain_config_filepath(name, rotation_id, CONFIG_STREAM))
