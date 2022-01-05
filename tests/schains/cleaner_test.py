import json
import os
import shutil
from pathlib import Path

import mock
import pytest

from dataclasses import dataclass

from skale.skale_manager import spawn_skale_manager_lib

from core.schains.cleaner import (
    delete_bls_keys,
    monitor,
    get_schains_on_node,
    remove_config_dir,
    remove_schain_volume, remove_schain_container,
    remove_ima_container
)
from core.schains.config import init_schain_config_dir
from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
from tools.configs.schains import SCHAINS_DIR_PATH
from web.models.schain import (
    SChainRecord, mark_schain_deleted, upsert_schain_record)


from tests.utils import (get_schain_contracts_data,
                         run_simple_schain_container,
                         run_simple_ima_container)

SCHAIN_CONTAINER_NAME_TEMPLATE = 'skale_schain_{}'
IMA_CONTAINER_NAME_TEMPLATE = 'skale_ima_{}'

TEST_SCHAIN_NAME_1 = 'schain_cleaner_test1'
TEST_SCHAIN_NAME_2 = 'schain_cleaner_test2'
PHANTOM_SCHAIN_NAME = 'phantom_schain'


@dataclass
class ImaEnv:
    schain_dir: str

    def to_dict(self):
        return {}


def is_container_running(dutils, container_name):
    return dutils.is_container_running(container_name)


@pytest.fixture
def schain_dirs_for_monitor():
    schain_dir_path2 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_1)
    schain_dir_path1 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_2)
    Path(schain_dir_path1).mkdir(parents=True, exist_ok=True)
    Path(schain_dir_path2).mkdir(parents=True, exist_ok=True)
    try:
        yield
    finally:
        shutil.rmtree(schain_dir_path1)
        shutil.rmtree(schain_dir_path2)


@pytest.fixture
def upsert_db(db):
    for name in [TEST_SCHAIN_NAME_1, TEST_SCHAIN_NAME_2, PHANTOM_SCHAIN_NAME]:
        upsert_schain_record(name)


def test_monitor(db, schain_dirs_for_monitor, skale, node_config, dutils):
    ensure_schain_removed_mock = mock.Mock()

    ensure_schain_removed_mock = mock.Mock(side_effect=ValueError)
    with mock.patch('core.schains.cleaner.ensure_schain_removed',
                    ensure_schain_removed_mock):
        monitor(skale, node_config, dutils=dutils)
        ensure_schain_removed_mock.assert_any_call(
            skale,
            TEST_SCHAIN_NAME_1,
            0,
            dutils=dutils
        )
        ensure_schain_removed_mock.assert_any_call(
            skale,
            TEST_SCHAIN_NAME_2,
            0,
            dutils=dutils
        )

    monitor(skale, node_config, dutils=dutils)
    assert [
        c.name
        for c in dutils.client.containers.list(
            filters={'name': 'skale_schains'}
        )
    ] == []


def test_remove_config_dir():
    schain_name = 'temp'
    init_schain_config_dir(schain_name)
    config_dir = os.path.join(SCHAINS_DIR_PATH, schain_name)
    assert os.path.isdir(config_dir)
    remove_config_dir(schain_name)
    assert not os.path.isdir(config_dir)


def test_remove_schain_volume(dutils, schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    dutils.create_data_volume(schain_name)
    assert dutils.is_data_volume_exists(schain_name)
    remove_schain_volume(schain_name, dutils=dutils)
    assert not dutils.is_data_volume_exists(schain_name)


@pytest.fixture
def schain_container(schain_config, ssl_folder, dutils):
    """ Creates and removes schain container """
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    run_simple_schain_container(schain_data, dutils)
    yield schain_name
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    dutils.safe_rm(get_container_name(SCHAIN_CONTAINER, schain_name),
                   force=True)
    dutils.safe_rm(get_container_name(IMA_CONTAINER, schain_name),
                   force=True)


def test_remove_schain_container(
    dutils,
    schain_config,
    cleanup_container,
    cert_key_pair
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    run_simple_schain_container(schain_data, dutils)
    container_name = SCHAIN_CONTAINER_NAME_TEMPLATE.format(schain_name)
    assert is_container_running(dutils, container_name)
    remove_schain_container(schain_name, dutils=dutils)
    assert not is_container_running(dutils, container_name)


def test_remove_ima_container(dutils, schain_container):
    schain_name = schain_container
    schain_data = get_schain_contracts_data(schain_name)
    with mock.patch('core.schains.runner.get_ima_env', return_value=ImaEnv(
        schain_dir='/'
    )):
        run_simple_ima_container(schain_data, dutils)
    container_name = IMA_CONTAINER_NAME_TEMPLATE.format(schain_name)
    assert is_container_running(dutils, container_name)
    remove_ima_container(schain_name, dutils=dutils)
    assert not is_container_running(dutils, container_name)


def test_remove_schain_record():
    SChainRecord.create_table()
    name = "test"
    SChainRecord.add(name)
    mark_schain_deleted(name)
    record = SChainRecord.to_dict(SChainRecord.get_by_name(name))
    assert record["is_deleted"]
    SChainRecord.drop_table()


@pytest.fixture
def invalid_secret_key_file(schain_dirs_for_monitor):
    schain_dir_path1 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_1)
    secret_key_filepath = os.path.join(schain_dir_path1,
                                       'secret_key_1.json')
    with open(secret_key_filepath, 'w') as secret_key_file:
        json.dump(None, secret_key_file)
    return


@pytest.fixture
def valid_secret_key_file(schain_dirs_for_monitor):
    schain_dir_path1 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_1)
    secret_key_filepath = os.path.join(schain_dir_path1,
                                       'secret_key_0.json')
    with open(secret_key_filepath, 'w') as secret_key_file:
        json.dump(
            {'key_share_name': 'BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0'},
            secret_key_file
        )
    return


def test_delete_bls_keys(skale, valid_secret_key_file):
    with mock.patch('core.schains.cleaner.SgxClient.delete_bls_key',
                    new=mock.Mock()) as delete_mock:
        delete_bls_keys(skale, TEST_SCHAIN_NAME_1)
        delete_mock.assert_called_with(
            'BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0')
        assert delete_mock.call_count == 1


def test_delete_bls_keys_with_invalid_secret_key(
    skale,
    invalid_secret_key_file,
    valid_secret_key_file
):
    """
    No exception but removing called only for 0 secret key
    secret_key_1.json - invalid, secret_key_2.json not exists
    """
    skale_for_test = spawn_skale_manager_lib(skale)
    skale_for_test.schains.get_last_rotation_id = lambda x: 2
    with mock.patch('core.schains.cleaner.SgxClient.delete_bls_key',
                    new=mock.Mock()) as delete_mock:
        delete_bls_keys(skale_for_test, TEST_SCHAIN_NAME_1)
        assert delete_mock.call_count == 1


def test_get_schains_on_node(schain_dirs_for_monitor,
                             dutils, schain_container, upsert_db):
    schain_name = schain_container
    result = get_schains_on_node(dutils)
    print(sorted([
        TEST_SCHAIN_NAME_1, TEST_SCHAIN_NAME_2,
        PHANTOM_SCHAIN_NAME, schain_name
    ]))
    assert result == sorted([
        TEST_SCHAIN_NAME_1, TEST_SCHAIN_NAME_2,
        PHANTOM_SCHAIN_NAME, schain_name
    ])
