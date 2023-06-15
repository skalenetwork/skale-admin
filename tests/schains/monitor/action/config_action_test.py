import shutil

import pytest

from core.schains.checks import ConfigChecks
from core.schains.config.directory import schain_config_dir
from core.schains.monitor.action import ConfigActionManager

from web.models.schain import SChainRecord


@pytest.fixture
def rotation_data(schain_db, skale):
    return skale.node_rotation.get_rotation(schain_db)


@pytest.fixture
def config_checks(
    schain_db,
    skale,
    node_config,
    schain_on_contracts,
    rotation_data
):
    name = schain_db
    schain_record = SChainRecord.get_by_name(name)
    return ConfigChecks(
        schain_name=name,
        node_id=node_config.id,
        schain_record=schain_record,
        rotation_id=rotation_data['rotation_id']
    )


@pytest.fixture
def config_am(
    schain_db,
    skale,
    node_config,
    schain_on_contracts,
    predeployed_ima,
    secret_key,
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
        checks=config_checks
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