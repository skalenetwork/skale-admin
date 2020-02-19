import pytest
from core.node_config import NodeConfig
from core.schains.monitor import SchainsMonitor
from tools.docker_utils import DockerUtils
from core.schains.runner import get_container_name, get_image_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
import mock
import time
import os


@pytest.fixture
def monitor(skale):
    config = NodeConfig()
    with mock.patch('core.schains.monitor.SchainsMonitor.wait_for_node_id'):
        monitor = SchainsMonitor(skale, config)
        monitor.node_id = 1
        return monitor


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


def run_cleanup_mock(skale, schain_name, node_id):
    os.remove(FILENAME)


def rotate_schain_mock(self, schain):
    os.remove(FILENAME)


FILENAME = "test.txt"
SCHAIN_NAME = 'test'
SCHAIN = {
    'name': SCHAIN_NAME,
    'owner': '0x1213123091a230923123213123',
    'indexInOwnerList': 0,
    'partOfNode': 0,
    'lifetime': 3600,
    'startDate': 1575448438,
    'deposit': 1000000000000000000,
    'index': 0,
    'active': True
}
CHECK_MOCK = {
    'data_dir': {'result': True},
    'dkg': {'result': True},
    'config': {'result': True},
    'volume': {'result': True},
    'container': {'result': True},
    'ima_container': {'result': True},
    'firewall_rules': {'result': True}
}


def test_rotate_schain(monitor, dutils):
    ima_container_name = get_container_name(IMA_CONTAINER, SCHAIN_NAME)
    schain_container_name = get_container_name(SCHAIN_CONTAINER, SCHAIN_NAME)
    ima_image = get_image_name(IMA_CONTAINER)
    schain_image = get_image_name(SCHAIN_CONTAINER)
    dutils.client.containers.run(schain_image, name=schain_container_name, detach=True)
    dutils.client.containers.run(ima_image, name=ima_container_name, detach=True)
    schain_cont = dutils.client.containers.get(schain_container_name)
    ima_cont = dutils.client.containers.get(ima_container_name)
    with mock.patch('core.schains.monitor.generate_schain_config'), \
            mock.patch('core.schains.monitor.save_schain_config'):
        monitor.rotate_schain(SCHAIN)
    restarted_schain = dutils.client.containers.get(schain_container_name)
    restarted_ima = dutils.client.containers.get(ima_container_name)
    assert schain_cont.attrs['State']['StartedAt'] != restarted_schain.attrs['State']['StartedAt']
    assert ima_cont.attrs['State']['StartedAt'] != restarted_ima.attrs['State']['StartedAt']
    monitor.scheduler.shutdown()


def test_exiting_monitor(monitor):
    delta_time = 10
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time() + delta_time
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    open(FILENAME, 'w').close()
    with mock.patch('core.schains.monitor.SChainRecord'), \
        mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0),\
        mock.patch('core.schains.monitor.SChainChecks.get_all',
                   new=mock.Mock(return_value=CHECK_MOCK)),\
        mock.patch('core.schains.monitor.run_cleanup',
                   new=run_cleanup_mock):
        monitor.monitor_schain(SCHAIN)
        assert len(monitor.scheduler.get_jobs()) == 1
        assert monitor.scheduler.get_jobs()[0].name == SCHAIN_NAME
        monitor.monitor_schain(SCHAIN)
        assert len(monitor.scheduler.get_jobs()) <= 1
        time.sleep(delta_time)
        assert not os.path.exists(FILENAME)


def test_rotating_monitor(monitor):
    delta_time = 20
    rotation_info = {
        'result': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time() + delta_time
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    open(FILENAME, 'w').close()
    with mock.patch('core.schains.monitor.SChainRecord'), \
        mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0),\
        mock.patch('core.schains.monitor.SChainChecks.get_all',
                   new=mock.Mock(return_value=CHECK_MOCK)),\
        mock.patch('core.schains.monitor.SchainsMonitor.rotate_schain',
                   new=rotate_schain_mock):
        monitor.monitor_schain(SCHAIN)
        assert len(monitor.scheduler.get_jobs()) == 1
        assert monitor.scheduler.get_jobs()[0].name == SCHAIN_NAME
        monitor.monitor_schain(SCHAIN)
        assert len(monitor.scheduler.get_jobs()) <= 1
        time.sleep(delta_time)
        assert not os.path.exists(FILENAME)
