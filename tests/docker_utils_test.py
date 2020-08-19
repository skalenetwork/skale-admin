import os
from functools import partial

import docker
import pytest
import time
import mock

from tools.docker_utils import DockerUtils
from core.schains.runner import (run_schain_container, run_ima_container,
                                 get_container_name, get_image_name)
from tools.configs.containers import SCHAIN_CONTAINER


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
def mocked_client():
    dutils = DockerUtils(volume_driver='local')
    dutils.get_all_schain_containers = partial(
        dutils.get_all_schain_containers,
        all=True
    )
    return dutils


@pytest.fixture
def client():
    return DockerUtils(volume_driver='local')


def run_simple_schain_container(dutils):
    run_schain_container(SCHAIN, dutils=dutils)


def run_simple_schain_container_in_sync_mode(dutils):
    public_key = "1:1:1:1"
    timestamp = time.time()

    class SnapshotAddressMock:
        def __init__(self):
            self.ip = '0.0.0.0'
            self.port = '8080'

    # Run schain container
    with mock.patch('core.schains.config_builder.get_skaled_http_snapshot_address',
                    return_value=SnapshotAddressMock()):
        run_schain_container(SCHAIN, public_key, timestamp, dutils=dutils)


def run_simple_ima_container(dutils):
    run_ima_container(SCHAIN, dutils=dutils)


def check_schain_container(client):
    assert client.data_volume_exists(SCHAIN_NAME)

    containers = client.get_all_schain_containers()
    assert len(containers) == 1
    containers = client.get_all_skale_containers()
    assert len(containers) == 1

    info = client.get_info(containers[0].id)
    assert 'stats' in info
    assert info['status'] == 'running'
    assert client.container_running(info)
    assert containers[0].name


def remove_schain_container(client):
    containers = client.get_all_schain_containers()
    name = containers[0].name
    client.safe_rm(name, force=True)
    client.rm_vol(SCHAIN_NAME)


def test_run_schain_container(client):
    # Run schain container
    run_simple_schain_container(client)

    # Perform container checks
    check_schain_container(client)

    # Remove container and volume
    remove_schain_container(client)


def test_run_schain_container_in_sync_mode(client):
    # Run schain container
    run_simple_schain_container_in_sync_mode(client)

    # Perform container checks
    check_schain_container(client)

    # Remove container and volume
    remove_schain_container(client)


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


def test_restart_all_schains(mocked_client):
    schain_names = ['test1', 'test2', 'test3']
    schain_image = get_image_name(SCHAIN_CONTAINER)
    cont_names = [get_container_name(SCHAIN_CONTAINER, name) for name in schain_names]
    start_time = {}

    def get_schain_time(cont_name):
        cont = mocked_client.client.containers.get(cont_name)
        return cont.attrs['State']['StartedAt']

    for cont_name in cont_names:
        mocked_client.client.containers.run(schain_image, name=cont_name, detach=True)
        start_time[cont_name] = get_schain_time(cont_name)
    mocked_client.restart_all_schains()
    for cont_name in cont_names:
        assert get_schain_time(cont_name) != start_time[cont_name]
    for cont_name in cont_names:
        mocked_client.client.containers.get(cont_name).remove(force=True)
