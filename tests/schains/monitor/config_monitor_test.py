import glob
import os

import pytest
from skale import SkaleIma, SkaleManager
from skale.types.rotation import Rotation
from skale.types.schain import SchainHash, SchainName
from skale.utils.helper import ip_to_bytes, schain_name_to_hash

from core.checks.schain import ConfigChecks
from core.config.schain.directory import schain_config_dir
from core.manager_cache import ManagerCache
from core.monitor.schain.action_config import ConfigActionManager
from core.monitor.schain.monitor_config import RegularConfigMonitor, SyncConfigMonitor
from core.node import get_current_nodes
from core.node_config import NodeConfig
from core.schains.external_config import ExternalConfig, ExternalState
from tests.utils import CONFIG_STREAM, generate_random_ip
from web.models.schain import SChainRecord


@pytest.fixture
def rotation_data(schain_db: SchainName, skale: SkaleManager) -> Rotation:
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def config_checks(
    schain_db: SchainName,
    skale: SkaleManager,
    node_config: NodeConfig,
    schain_hash_on_contracts: SchainHash,
    rotation_data: Rotation,
    estate: ExternalState,
    manager_cache: ManagerCache,
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts, manager_cache)
    return ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        rotation_id=rotation_data.rotation_counter,
        stream_version=CONFIG_STREAM,
        current_nodes=current_nodes,
        last_dkg_successful=True,
        estate=estate,
    )


@pytest.fixture
def config_am(
    schain_db: SchainName,
    skale: SkaleManager,
    node_config: NodeConfig,
    schain_hash_on_contracts: SchainHash,
    secret_key,
    config_checks: ConfigChecks,
    estate: ExternalState,
    skale_ima: SkaleIma,
    manager_cache: ManagerCache,
):
    name = schain_db
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)
    current_nodes = get_current_nodes(skale, schain_hash_on_contracts, manager_cache)

    am = ConfigActionManager(
        skale=skale,
        skale_ima=skale_ima,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        stream_version=CONFIG_STREAM,
        checks=config_checks,
        current_nodes=current_nodes,
        estate=estate,
    )
    am.dkg = lambda s: True
    return am


@pytest.fixture
def regular_config_monitor(config_am, config_checks):
    return RegularConfigMonitor(action_manager=config_am, checks=config_checks)


@pytest.fixture
def sync_config_monitor(config_am, config_checks):
    return SyncConfigMonitor(action_manager=config_am, checks=config_checks)


def test_regular_config_monitor(schain_db, regular_config_monitor, rotation_data):
    name = schain_db
    rotation_id = rotation_data.rotation_counter

    regular_config_monitor.run()
    config_dir = schain_config_dir(name)

    pattern = os.path.join(config_dir, f'schain_{name}_{rotation_id}_*.json')
    filenames = glob.glob(pattern)
    assert os.path.isfile(filenames[0])


def test_regular_config_monitor_change_ip(
    skale: SkaleManager,
    schain_db: SchainName,
    regular_config_monitor: RegularConfigMonitor,
    rotation_data: Rotation,
    manager_cache: ManagerCache,
):
    name = schain_db
    schain_hash = schain_name_to_hash(name)
    econfig = ExternalConfig(name=name)
    assert econfig.reload_ts is None

    regular_config_monitor.run()
    assert econfig.reload_ts is None

    current_nodes = get_current_nodes(skale, schain_hash, manager_cache)
    new_ip = generate_random_ip()
    skale.nodes.change_ip(current_nodes[0]['id'], ip_to_bytes(new_ip), ip_to_bytes(new_ip))

    current_nodes = get_current_nodes(skale, schain_hash, manager_cache)
    regular_config_monitor.am.current_nodes = current_nodes
    regular_config_monitor.checks.current_nodes = current_nodes

    regular_config_monitor.run()
    assert econfig.reload_ts is not None
    assert econfig.reload_ts > 0

    current_nodes = get_current_nodes(skale, schain_hash, manager_cache)
    regular_config_monitor.am.current_nodes = current_nodes
    regular_config_monitor.checks.current_nodes = current_nodes

    regular_config_monitor.am.cfm.sync_skaled_config_with_upstream()
    regular_config_monitor.run()
    assert econfig.reload_ts is None


def test_sync_config_monitor(
    skale: SkaleManager,
    schain_db: SchainName,
    config_am: ConfigActionManager,
    config_checks: ConfigChecks,
    econfig: ExternalConfig,
    estate: ExternalState,
    rotation_data: Rotation,
):
    name = schain_db
    config_dir = schain_config_dir(name)

    rotation_id = rotation_data.rotation_counter
    config_pattern = os.path.join(config_dir, f'schain_{name}_{rotation_id}_*.json')
    assert len(glob.glob(config_pattern)) == 0

    assert econfig.synced(estate)

    estate.chain_id = 1
    config_checks.estate = estate
    config_am.estate = estate
    assert not econfig.synced(estate)

    sync_config_monitor = SyncConfigMonitor(action_manager=config_am, checks=config_checks)
    sync_config_monitor.run()
    assert econfig.synced(estate)
    config_filename = glob.glob(config_pattern)
    assert os.path.isfile(config_filename[0])


def test_sync_config_monitor_dkg_not_completed(
    skale: SkaleManager,
    schain_db: SchainName,
    config_am: ConfigActionManager,
    config_checks: ConfigChecks,
    econfig: ExternalConfig,
    estate: ExternalState,
    rotation_data: Rotation,
):
    name = schain_db
    config_dir = schain_config_dir(name)

    rotation_id = rotation_data.rotation_counter
    config_pattern = os.path.join(config_dir, f'schain_{name}_{rotation_id}_*.json')
    assert len(glob.glob(config_pattern)) == 0

    assert econfig.synced(estate)

    estate.chain_id = 1
    config_checks.estate = estate
    config_am.estate = estate
    config_checks._last_dkg_successful = False
    assert not econfig.synced(estate)

    sync_config_monitor = SyncConfigMonitor(action_manager=config_am, checks=config_checks)
    sync_config_monitor.run()
    assert econfig.synced(estate)
    # config generation was not triggered because dkg has not been completed
    assert len(glob.glob(config_pattern)) == 0
