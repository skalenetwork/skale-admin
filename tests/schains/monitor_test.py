import pytest
from core.node_config import NodeConfig
from core.schains.monitor import SchainsMonitor, run_schain_container, run_ima_container
from tools.docker_utils import DockerUtils
from core.schains.runner import get_container_name, get_image_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
import mock


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
