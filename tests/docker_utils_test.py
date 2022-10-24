import os
from functools import partial

import docker
import pytest
from mock import Mock
from types import SimpleNamespace

from core.schains.runner import (
    get_container_name,
    get_image_name,
    get_container_info
)
from tests.utils import (
    get_schain_contracts_data,
    run_simple_schain_container,
    run_simple_schain_container_in_sync_mode
)
from tools.configs.containers import SCHAIN_CONTAINER
from tools.configs import NODE_DATA_PATH
from tools.docker_utils import DockerUtils

from unittest import mock


DIR_PATH = os.path.dirname(os.path.realpath(__file__))
TEST_SKALE_DATA_DIR = os.path.join(DIR_PATH, 'skale-data')
ENDPOINT = os.getenv('ENDPOINT')
ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
HELLO_MSG = 'Hello, SKALE!'
LOGS_TEST_LINES = [
    f'{HELLO_MSG}\n',
    '================================================================================\n',   # noqa
    f'{HELLO_MSG}\n'
]


@pytest.fixture
def mocked_dutils(dutils):
    dutils.get_all_schain_containers = partial(
        dutils.get_all_schain_containers,
        all=True
    )
    return dutils


def check_schain_container(schain_name: str, client: DockerUtils):
    assert client.is_data_volume_exists(schain_name)

    containers = client.get_all_skale_containers()
    assert len(containers) == 1

    containers = client.get_all_schain_containers()
    assert len(containers) == 1

    info = client.get_info(containers[0].id)
    assert 'stats' in info
    print('DEBUG', containers[0].logs())
    assert info['status'] == 'running'
    assert client.is_container_running(containers[0].id)
    assert containers[0].name


@pytest.fixture
def cleanup_container(schain_config, dutils):
    yield
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    dutils.safe_rm(
        get_container_name(SCHAIN_CONTAINER, schain_name),
        force=True
    )


def remove_schain_container(schain_name, client):
    containers = client.get_all_schain_containers()
    if containers:
        name = containers[0].name
        client.safe_rm(name, force=True)
    client.rm_vol(schain_name)


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
def test_run_schain_container(
    get_image,
    dutils,
    schain_config,
    cleanup_container,
    cert_key_pair,
    skaled_mock_image
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    # Run schain container
    run_simple_schain_container(schain_data, dutils)

    # Perform container checks
    check_schain_container(schain_name, dutils)


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
def test_run_schain_container_in_sync_mode(
    get_image,
    dutils,
    schain_config,
    cleanup_container,
    cert_key_pair,
    skaled_mock_image
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_data = get_schain_contracts_data(schain_name)
    # Run schain container
    run_simple_schain_container_in_sync_mode(schain_data, dutils)

    # Perform container checks
    check_schain_container(schain_name, dutils)


def test_not_existed_docker_objects(dutils):
    # Not existed volume
    assert not dutils.is_data_volume_exists('random_name')
    # No exception
    dutils.rm_vol('random_name')

    # Not existed container
    info = dutils.get_info('random_id')
    assert info['status'] == 'not_found'
    assert dutils.is_container_found('random_id') is False
    dutils.safe_rm('random_name')


def test_restart_all_schains(mocked_dutils):
    schain_names = ['test1', 'test2', 'test3']
    schain_image = get_image_name(SCHAIN_CONTAINER)
    cont_names = [
        get_container_name(SCHAIN_CONTAINER, name)
        for name in schain_names
    ]
    start_time = {}

    def get_schain_time(cont_name):
        cont = mocked_dutils.client.containers.get(cont_name)
        return cont.attrs['State']['StartedAt']

    for cont_name in cont_names:
        mocked_dutils.client.containers.run(
            schain_image,
            name=cont_name, detach=True
        )
        start_time[cont_name] = get_schain_time(cont_name)
    mocked_dutils.restart_all_schains()
    for cont_name in cont_names:
        assert get_schain_time(cont_name) != start_time[cont_name]
    for cont_name in cont_names:
        mocked_dutils.client.containers.get(cont_name).remove(force=True)


def test_safe_rm(dutils):
    _, container_name = run_test_schain_container(dutils)
    container = dutils.client.containers.get(container_name)
    path = dutils.get_logs_backup_filepath(container)
    assert not os.path.isfile(path)
    assert dutils.safe_get_container(container_name)
    dutils.safe_rm(container_name)
    assert os.path.isfile(path)
    with open(path) as f:
        assert f.readlines() == LOGS_TEST_LINES
    assert not dutils.safe_get_container(container_name)


def test_get_logs_backup_filepath(dutils):
    ls = []
    container_mock = SimpleNamespace(name='skale_schain_test')
    with mock.patch('os.listdir', return_value=ls):
        path = dutils.get_logs_backup_filepath(container_mock)
    assert path == os.path.join(
        NODE_DATA_PATH,
        'log/.removed_containers/skale_schain_test-0.log'
    )

    ls = [
        'skale_schain_test-0.log',
        'skale_schain_test-1.log',
        'skale_schain_testgg-0.log'
    ]
    with mock.patch('os.listdir', return_value=ls):
        path = dutils.get_logs_backup_filepath(container_mock)
    assert path == os.path.join(
        NODE_DATA_PATH,
        'log/.removed_containers/skale_schain_test-2.log'
    )


def run_test_schain_container(dutils):
    test_schain_name = 'test_container'
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER,
        test_schain_name
    )
    container = dutils.safe_get_container(container_name)
    if container:
        container.remove(v=True, force=True)
    try:
        dutils.run_container(
            image_name=image_name,
            name=container_name,
            entrypoint=f'echo {HELLO_MSG}'
        )
    except Exception as e:
        container = dutils.safe_get_container(container_name)
        if container:
            container.remove(v=True, force=True)
        raise e
    return test_schain_name, container_name


def test_remove_volume(dutils):
    name = 'test'
    dutils.client.volumes.create(name=name)
    dutils.rm_vol(name)
    with pytest.raises(docker.errors.APIError):
        dutils.client.volumes.get(name)


def test_remove_volume_error(dutils):
    name = 'test'
    dutils.client.volumes.create(name=name)
    volume_mock = Mock()
    volume_mock.remove = Mock(side_effect=docker.errors.APIError('test error'))
    dutils.get_vol = Mock(return_value=volume_mock)
    with pytest.raises(docker.errors.APIError):
        dutils.rm_vol(name, retry_lvmpy_error=False)
