import shutil

import pytest

from core.schains.checks import ConfigChecks
from core.schains.config.directory import schain_config_dir
from core.schains.monitor.action import ConfigActionManager
from core.schains.external_config import ExternalConfig
from tools.helper import read_json
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
    estate,
    rotation_data
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
    estate,
    config_checks
):
    name = schain_db
    rotation_data = skale.node_rotation.get_rotation(name)
    schain = skale.schains.get_by_name(name)
    return ConfigActionManager(
        skale=skale,
        schain=schain,
        node_config=node_config,
        rotation_data=rotation_data,
        checks=config_checks,
        stream_version=CONFIG_STREAM,
        estate=estate
    )


def test_upstream_config_actions(config_am, config_checks):
    config_am.config_dir()
    assert config_checks.config_dir
    assert not config_checks.upstream_config

    # Folder created for secret key. Temporary moving
    schain_folder = schain_config_dir(config_am.name)
    tmp_schain_folder = '.' + schain_folder
    try:
        shutil.move(schain_folder, tmp_schain_folder)
        assert not config_checks.config_dir
        assert not config_checks.upstream_config
    finally:
        shutil.move(tmp_schain_folder, schain_folder)

    # DKG action is tested separetely in dkg_test module

    config_am.config_dir()
    config_am.upstream_config()
    assert config_checks.config_dir
    assert config_checks.upstream_config

    # Try to recreate config with no changes
    config_am.upstream_config()
    assert config_checks.upstream_config


@pytest.fixture
def empty_econfig(schain_db):
    name = schain_db
    return ExternalConfig(name)


def test_external_state_config_actions(config_am, config_checks, empty_econfig):
    config_am.config_dir()
    assert not config_checks.external_state
    assert config_am.external_state()
    econfig_data = read_json(empty_econfig.path)
    assert econfig_data == {
        'ima_linked': True,
        'chain_id': config_am.skale.web3.eth.chain_id,
        'ranges': [['1.1.1.1', '2.2.2.2'], ['3.3.3.3', '4.4.4.4']]
    }
    assert config_checks.external_state
