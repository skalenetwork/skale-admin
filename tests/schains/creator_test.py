import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from core.node_config import NodeConfig
from core.schains.creator import monitor_schain
from core.schains.helper import get_schain_config_filepath
from tools.docker_utils import DockerUtils
from tools.configs import TEMP_CONFIG_EXTENSION
import mock
import time
import os


@pytest.fixture
def config(skale):
    config = NodeConfig()
    return config


@pytest.fixture
def scheduler():
    scheduler = BackgroundScheduler()
    scheduler.start()
    yield scheduler
    scheduler.shutdown()


@pytest.fixture
def dutils():
    return DockerUtils(volume_driver='local')


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


def test_exiting_monitor(skale, config, scheduler):
    node_id = config.id
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('core.schains.creator.SChainRecord'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0),\
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)),\
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        monitor_schain(skale, node_id, 'test', SCHAIN)
        rotation.assert_called_with(SCHAIN, rotation_info['finish_ts'], is_exit=True)


def test_rotating_monitor(skale, config, scheduler):
    node_id = config.id
    rotation_info = {
        'result': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('core.schains.creator.SChainRecord'),\
            mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.generate_schain_config',
                       new=mock.Mock(return_value=True)), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        monitor_schain(skale, node_id, 'test', SCHAIN)
        config_path = get_schain_config_filepath(SCHAIN['name']) + TEMP_CONFIG_EXTENSION
        rotation.assert_called_with(SCHAIN, rotation_info['finish_ts'])
        assert os.path.exists(config_path)
        os.remove(config_path)


def test_new_schain_monitor(skale, config, scheduler):
    node_id = config.id
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    CHECK_MOCK['container'] = False
    with mock.patch('core.schains.creator.SChainRecord'), \
            mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.monitor_sync_schain_container',
                       new=mock.Mock()) as sync:
        monitor_schain(skale, node_id, 'test', SCHAIN)
        args, kwargs = sync.call_args
        assert args[1] == SCHAIN
        assert args[2] == rotation_info['finish_ts']
