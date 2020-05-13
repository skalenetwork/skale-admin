import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from core.node_config import NodeConfig
from core.schains.creator import rotate_schain, monitor_schain
from tools.docker_utils import DockerUtils
from core.schains.runner import get_container_name, get_image_name
from tools.configs.containers import SCHAIN_CONTAINER, IMA_CONTAINER
import mock
import time
import os


@pytest.fixture
def node_id(skale):
    config = NodeConfig()
    return config.id


@pytest.fixture
def scheduler():
    scheduler = BackgroundScheduler()
    scheduler.start()
    yield scheduler
    scheduler.shutdown()


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


def cleanup_schain_mock(skale, schain_name, node_id):
    os.remove(FILENAME)


def rotate_schain_mock(self, node_id, schain, rotation_id):
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
    'data_dir': True,
    'dkg': True,
    'config': True,
    'volume': True,
    'container': True,
    'ima_container': True,
    'firewall_rules': True
}


def test_rotate_schain(skale, node_id, dutils):
    ima_container_name = get_container_name(IMA_CONTAINER, SCHAIN_NAME)
    schain_container_name = get_container_name(SCHAIN_CONTAINER, SCHAIN_NAME)
    ima_image = get_image_name(IMA_CONTAINER)
    schain_image = get_image_name(SCHAIN_CONTAINER)
    dutils.client.containers.run(schain_image, name=schain_container_name, detach=True)
    dutils.client.containers.run(ima_image, name=ima_container_name, detach=True)
    schain_cont = dutils.client.containers.get(schain_container_name)
    ima_cont = dutils.client.containers.get(ima_container_name)
    with mock.patch('core.schains.creator.generate_schain_config'), \
            mock.patch('core.schains.creator.save_schain_config'):
        rotate_schain(skale, node_id, SCHAIN, 0)
    restarted_schain = dutils.client.containers.get(schain_container_name)
    restarted_ima = dutils.client.containers.get(ima_container_name)
    assert schain_cont.attrs['State']['StartedAt'] != restarted_schain.attrs['State']['StartedAt']
    assert ima_cont.attrs['State']['StartedAt'] != restarted_ima.attrs['State']['StartedAt']


def test_exiting_monitor(skale, scheduler):
    delta_time = 10
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time() + delta_time,
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    open(FILENAME, 'w').close()
    with mock.patch('core.schains.creator.SChainRecord'), \
        mock.patch('core.schains.creator.CONTAINERS_DELAY', 0),\
        mock.patch('core.schains.creator.SChainChecks.run_checks'), \
        mock.patch('core.schains.creator.SChainChecks.get_all',
                   new=mock.Mock(return_value=CHECK_MOCK)),\
        mock.patch('core.schains.creator.cleanup_schain',
                   new=cleanup_schain_mock):
        monitor_schain(skale, node_id, 'test', SCHAIN, scheduler)
        assert len(scheduler.get_jobs()) == 1
        assert scheduler.get_jobs()[0].name == SCHAIN_NAME
        monitor_schain(skale, node_id, 'test', SCHAIN, scheduler)
        assert len(scheduler.get_jobs()) <= 1
        time.sleep(delta_time)
        assert not os.path.exists(FILENAME)


def test_rotating_monitor(skale, node_id, scheduler):
    delta_time = 20
    rotation_info = {
        'result': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time() + delta_time,
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    open(FILENAME, 'w').close()
    with mock.patch('core.schains.creator.SChainRecord'),\
        mock.patch('core.schains.creator.run_dkg'), \
        mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
        mock.patch('core.schains.creator.SChainChecks.run_checks'), \
        mock.patch('core.schains.creator.SChainChecks.get_all',
                   new=mock.Mock(return_value=CHECK_MOCK)),\
        mock.patch('core.schains.creator.rotate_schain',
                   new=rotate_schain_mock):
        monitor_schain(skale, node_id, 'test', SCHAIN, scheduler)
        assert len(scheduler.get_jobs()) == 1
        assert scheduler.get_jobs()[0].name == SCHAIN_NAME
        monitor_schain(skale, node_id, 'test', SCHAIN, scheduler)
        assert len(scheduler.get_jobs()) <= 1
        time.sleep(delta_time)
        assert not os.path.exists(FILENAME)
