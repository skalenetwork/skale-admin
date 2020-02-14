import pytest
from core.node_config import NodeConfig
from core.schains.monitor import SchainsMonitor, run_schain_container, run_ima_container
from tools.docker_utils import DockerUtils
from core.schains.runner import get_container_name, get_image_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER


@pytest.fixture
def monitor(skale):
    config = NodeConfig()
    monitor = SchainsMonitor(skale, config)
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
    schain_cont = dutils.client.containers.run(schain_image, name=schain_container_name, detach=True)
    ima_cont = dutils.client.containers.run(ima_image, name=ima_container_name, detach=True)
    monitor.rotate(SCHAIN)
