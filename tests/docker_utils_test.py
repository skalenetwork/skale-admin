import os

import docker
import pytest

from tools.docker_utils import DockerUtils
from core.schains.runner import (run_schain_container, run_ima_container,
                                 run_schain_container_in_sync_mode)


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
TEST_SKALE_DATA_DIR = os.path.join(DIR_PATH, 'skale-data')
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.path.join(DIR_PATH, 'test_abi.json')


SCHAIN_NAME = 'test'
SCHAIN = {
    'name': SCHAIN_NAME,
    'owner': '0x1213123091i230923123213123',
    'indexInOwnerList': 0,
    'partOfNode': 0,
    'lifetime': 3600,
    'startDate': 1575448438,
    'deposit': 1000000000000000000,
    'index': 0,
    'active': True
}


@pytest.fixture
def client():
    return DockerUtils(volume_driver='local')


def run_test_schain_container(dutils):
    env = {
        "SSL_KEY_PATH": 'NULL',
        "SSL_CERT_PATH": 'NULL',
        "HTTP_RPC_PORT": 10002,
        "HTTPS_RPC_PORT": 10007,
        "WS_RPC_PORT": 10003,
        "WSS_RPC_PORT": 10008,

        "SCHAIN_ID": SCHAIN_NAME,
        "CONFIG_FILE": os.path.join(TEST_SKALE_DATA_DIR, 'schain_config.json'),
        "DATA_DIR": '/data_dir'
    }
    # Run schain container
    run_schain_container(SCHAIN, env, dutils=dutils)


def test_run_schain_container_in_sync_mode(dutils):
    env = {
        "SSL_KEY_PATH": 'NULL',
        "SSL_CERT_PATH": 'NULL',
        "HTTP_RPC_PORT": 10002,
        "HTTPS_RPC_PORT": 10007,
        "WS_RPC_PORT": 10003,
        "WSS_RPC_PORT": 10008,

        "SCHAIN_ID": SCHAIN_NAME,
        "CONFIG_FILE": os.path.join(TEST_SKALE_DATA_DIR, 'schain_config.json'),
        "DATA_DIR": '/data_dir'
    }
    # Run schain container
    run_schain_container_in_sync_mode(SCHAIN, env, dutils=dutils)


def run_test_ima_container(dutils):
    run_ima_container(SCHAIN, {})


def test_run_schain_container(client):
    # Run schain container
    run_test_schain_container(client)

    # Perform container checks
    assert client.data_volume_exists(SCHAIN_NAME)

    containers = client.get_all_schain_containers()
    assert len(containers) == 1
    containers = client.get_all_skale_containers()
    assert len(containers) == 1

    info = client.get_info(containers[0].id)
    assert 'stats' in info
    assert info['status'] == 'running'
    assert client.container_running(info)

    # Remove container and volume
    assert containers[0].name
    client.safe_rm(containers[0].name, force=True)
    client.rm_vol(SCHAIN_NAME)


def test_not_existed_docker_objects(client):
    # Not existed volume
    assert not client.data_volume_exists('random_name')
    with pytest.raises(docker.errors.NotFound):
        client.rm_vol('random_name')

    # Not existed container
    info = client.get_info('random_id')
    assert info['status'] == 'not_found'
    assert client.to_start_container(info)
    client.safe_rm('random_name')
