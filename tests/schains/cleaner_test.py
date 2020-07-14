import os
from unittest import mock

import pytest

from core.schains.cleaner import (remove_config_dir, remove_schain_volume, remove_schain_container,
                                  remove_ima_container, delete_bls_keys)
from core.schains.helper import init_schain_dir
from tools.configs.schains import SCHAINS_DIR_PATH

from tools.docker_utils import DockerUtils

from tests.docker_utils_test import run_simple_schain_container, run_simple_ima_container, SCHAIN
from web.models.schain import SChainRecord, mark_schain_deleted

SCHAIN_CONTAINER_NAME = 'skale_schain_test'
IMA_CONTAINER_NAME = 'skale_ima_test'


def container_running(dutils, container_name):
    info = dutils.get_info(container_name)
    return dutils.container_running(info)


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


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


def test_remove_schain_container(dutils):
    run_simple_schain_container(dutils)
    assert container_running(dutils, SCHAIN_CONTAINER_NAME)
    remove_schain_container(SCHAIN['name'])
    assert not container_running(dutils, SCHAIN_CONTAINER_NAME)


def test_remove_ima_container(dutils):
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


def test_delete_bls_keys(skale):
    with mock.patch('core.schains.cleaner.SgxClient.delete_bls_key',
                    new=mock.Mock()) as delete_mock:
        delete_bls_keys(skale, SCHAIN['name'])
        delete_mock.assert_called_with('BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0')
