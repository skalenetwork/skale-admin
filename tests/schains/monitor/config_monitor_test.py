import glob
import os

import pytest
from skale.utils.helper import ip_to_bytes

from core.node import get_current_nodes

from core.schains.checks import ConfigChecks
from core.schains.config.directory import schain_config_dir

from core.schains.monitor.action import ConfigActionManager
from core.schains.monitor.config_monitor import RegularConfigMonitor
from core.schains.external_config import ExternalConfig

from web.models.schain import SChainRecord

from tests.utils import CONFIG_STREAM, generate_random_ip


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
    current_nodes = get_current_nodes(skale, name)
    return ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        rotation_id=rotation_data['rotation_id'],
        stream_version=CONFIG_STREAM,
        current_nodes=current_nodes,
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
    current_nodes = get_current_nodes(skale, name)

    am = ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=CONFIG_STREAM,
        checks=config_checks,
        current_nodes=current_nodes,
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
    config_dir = schain_config_dir(name)

    pattern = os.path.join(
        config_dir,
        f'schain_{name}_{rotation_id}_*.json'
    )
    filenames = glob.glob(pattern)
    assert os.path.isfile(filenames[0])


def test_regular_config_monitor_change_ip(
    skale,
    schain_db,
    regular_config_monitor,
    rotation_data
):
    name = schain_db
    econfig = ExternalConfig(name=name)
    assert econfig.reload_ts is None

    regular_config_monitor.run()
    assert econfig.reload_ts is None

    current_nodes = get_current_nodes(skale, name)
    new_ip = generate_random_ip()
    skale.nodes.change_ip(current_nodes[0]['id'], ip_to_bytes(new_ip), ip_to_bytes(new_ip))

    current_nodes = get_current_nodes(skale, name)
    regular_config_monitor.am.current_nodes = current_nodes
    regular_config_monitor.checks.current_nodes = current_nodes

    regular_config_monitor.run()
    assert econfig.reload_ts is not None
    assert econfig.reload_ts > 0

    current_nodes = get_current_nodes(skale, name)
    regular_config_monitor.am.current_nodes = current_nodes
    regular_config_monitor.checks.current_nodes = current_nodes

    regular_config_monitor.am.cfm.sync_skaled_config_with_upstream()
    regular_config_monitor.run()
    assert econfig.reload_ts is None
