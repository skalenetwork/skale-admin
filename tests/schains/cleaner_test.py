import os
import shutil
from pathlib import Path

import mock
import pytest

from core.node_config import NodeConfig
from core.schains.cleaner import (monitor, remove_config_dir,
                                  remove_schain_volume, remove_schain_container,
                                  remove_ima_container, delete_bls_keys)
from core.schains.helper import init_schain_dir
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord, mark_schain_deleted

from tests.docker_utils_test import run_simple_schain_container, run_simple_ima_container, SCHAIN
from tests.utils import generate_random_schain_data

SCHAIN_CONTAINER_NAME = 'skale_schain_test'
IMA_CONTAINER_NAME = 'skale_ima_test'


def container_running(dutils, container_name):
    info = dutils.get_info(container_name)
    return dutils.container_running(info)


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


@pytest.fixture
def node_config(skale):
    node_config = NodeConfig()
    node_config.id = 0
    return node_config


TEST_SCHAIN_NAME_1 = 'cleaner_test1'
TEST_SCHAIN_NAME_2 = 'cleaner_test2'


def create_test_schain_on_contracts(skale):
    type_of_nodes, lifetime_seconds, name = generate_random_schain_data()
    price_in_wei = skale.schains.get_schain_price(type_of_nodes,
                                                  lifetime_seconds)
    skale.manager.create_schain(lifetime_seconds, type_of_nodes,
                                price_in_wei, name)
    return name


@pytest.fixture
def schain_dirs_for_monitor():
    schain_dir_path2 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_1)
    schain_dir_path1 = os.path.join(SCHAINS_DIR_PATH, TEST_SCHAIN_NAME_2)
    Path(schain_dir_path1).mkdir(parents=True, exist_ok=False)
    Path(schain_dir_path2).mkdir(parents=True, exist_ok=False)
    yield
    shutil.rmtree(schain_dir_path1)
    shutil.rmtree(schain_dir_path2)


def test_monitor(schain_dirs_for_monitor, skale, node_config):
    ensure_schain_removed_mock = mock.Mock()

    with mock.patch('core.schains.cleaner.ensure_schain_removed',
                    ensure_schain_removed_mock):
        monitor(skale, node_config)
        assert ensure_schain_removed_mock.call_count == 2
        ensure_schain_removed_mock.assert_any_call(skale, TEST_SCHAIN_NAME_1, 0)
        ensure_schain_removed_mock.assert_any_call(skale, TEST_SCHAIN_NAME_2, 0)

    ensure_schain_removed_mock = mock.Mock(side_effect=ValueError)
    with mock.patch('core.schains.cleaner.ensure_schain_removed',
                    ensure_schain_removed_mock):
        monitor(skale, node_config)
        assert ensure_schain_removed_mock.call_count == 2
        ensure_schain_removed_mock.assert_any_call(skale, TEST_SCHAIN_NAME_1, 0)
        ensure_schain_removed_mock.assert_any_call(skale, TEST_SCHAIN_NAME_2, 0)


def test_remove_config_dir():
    schain_name = 'temp'
    init_schain_dir(schain_name)
    config_dir = os.path.join(SCHAINS_DIR_PATH, schain_name)
    assert os.path.isdir(config_dir)
    remove_config_dir(schain_name)
    assert not os.path.isdir(config_dir)


def test_remove_schain_volume(dutils):
    dutils.create_data_volume(SCHAIN['name'])
    assert dutils.data_volume_exists(SCHAIN['name'])
    remove_schain_volume(SCHAIN['name'])
    assert not dutils.data_volume_exists(SCHAIN['name'])


def test_remove_schain_container(dutils, schain_dir):
    run_simple_schain_container(dutils)
    assert container_running(dutils, SCHAIN_CONTAINER_NAME)
    remove_schain_container(SCHAIN['name'])
    assert not container_running(dutils, SCHAIN_CONTAINER_NAME)


def test_remove_ima_container(dutils, schain_dir):
    with mock.patch('core.schains.runner.get_ima_env', return_value={}):
        run_simple_ima_container(dutils)
    assert container_running(dutils, IMA_CONTAINER_NAME)
    remove_ima_container(SCHAIN['name'])
    assert not container_running(dutils, IMA_CONTAINER_NAME)


def test_remove_schain_record():
    SChainRecord.create_table()
    name = "test"
    SChainRecord.add(name)
    mark_schain_deleted(name)
    record = SChainRecord.to_dict(SChainRecord.get_by_name(name))
    assert record["is_deleted"]
    SChainRecord.drop_table()


def test_delete_bls_keys(skale, schain_dir):
    with mock.patch('core.schains.cleaner.SgxClient.delete_bls_key',
                    new=mock.Mock()) as delete_mock:
        delete_bls_keys(skale, SCHAIN['name'])
        delete_mock.assert_called_with('BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0')
