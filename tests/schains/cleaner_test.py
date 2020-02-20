import os
import pytest

from core.schains.cleaner import (remove_config_dir, remove_schain_volume, remove_schain_container,
                                  remove_ima_container)
from core.schains.helper import init_schain_dir
from tools.configs.schains import SCHAINS_DIR_PATH

from tools.docker_utils import DockerUtils

from tests.docker_utils_test import run_simple_schain_container, run_simple_ima_container, SCHAIN


SCHAIN_CONFIG_DIR = os.path.join(SCHAINS_DIR_PATH, SCHAIN['name'])
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
IMA_CONTAINER_NAME = 'skale_ima_test'


def container_running(dutils, container_name):
    info = dutils.get_info(container_name)
    return dutils.container_running(info)


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


def test_remove_config_dir():
    init_schain_dir(SCHAIN['name'])
    assert os.path.isdir(SCHAIN_CONFIG_DIR)
    remove_config_dir(SCHAIN['name'])
    assert not os.path.isdir(SCHAIN_CONFIG_DIR)


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
