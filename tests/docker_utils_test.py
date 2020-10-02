import os
from functools import partial

import docker
import pytest

from core.schains.runner import get_container_name, get_image_name
from tests.utils import (get_schain_contracts_data,
                         run_simple_schain_container,
                         run_simple_schain_container_in_sync_mode)
from tools.configs.containers import SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
TEST_SKALE_DATA_DIR = os.path.join(DIR_PATH, 'skale-data')
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
TEST_ABI_FILEPATH = os.path.join(DIR_PATH, 'test_abi.json')


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


def check_schain_container(schain_name: str, client: DockerUtils):
    assert client.is_data_volume_exists(schain_name)

    containers = client.get_all_schain_containers()
    assert len(containers) == 1
    containers = client.get_all_skale_containers()
    assert len(containers) == 1

    info = client.get_info(containers[0].id)
    assert 'stats' in info
    assert info['status'] == 'running'
    assert client.container_running(info)
    assert containers[0].name


@pytest.fixture
def cleanup_container(schain_config, client):
    yield
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    client.safe_rm(get_container_name(SCHAIN_CONTAINER, schain_name),
                   force=True)


def remove_schain_container(schain_name, client):
    containers = client.get_all_schain_containers()
    if containers:
        name = containers[0].name
        client.safe_rm(name, force=True)
    client.rm_vol(schain_name)


def test_run_schain_container(client, schain_config, cleanup_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    # Run schain container
    run_simple_schain_container(schain_data, client)

    # Perform container checks
    check_schain_container(schain_name, client)


def test_run_schain_container_in_sync_mode(client, schain_config,
                                           cleanup_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    # Run schain container
    run_simple_schain_container_in_sync_mode(schain_data, client)

    # Perform container checks
    check_schain_container(schain_name, client)


def test_not_existed_docker_objects(client):
    # Not existed volume
    assert not client.is_data_volume_exists('random_name')
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
