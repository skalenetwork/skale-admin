import pytest

from core.node_config import NodeConfig
from core.schains.creator import monitor_schain
from tools.docker_utils import DockerUtils
import mock
import time


# TODO: Add exited container test

@pytest.fixture
def config(skale):
    config = NodeConfig()
    return config


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


def test_exiting_monitor(skale, config):
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('web.models.schain.SChainRecord'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0),\
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)),\
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = config.all()
        monitor_schain(skale, node_info, SCHAIN, ecdsa_sgx_key_name='test')
        rotation.assert_called_with(SCHAIN, rotation_info['finish_ts'])


def test_rotating_monitor(skale, config):
    rotation_info = {
        'result': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('web.models.schain.SChainRecord'),\
            mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.generate_schain_config_with_skale',
                       new=mock.Mock(return_value=True)), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = config.all()
        monitor_schain(skale, node_info, SCHAIN, ecdsa_sgx_key_name='test')
        rotation.assert_called_with(SCHAIN, rotation_info['finish_ts'])


def test_new_schain_monitor(skale, config):
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    CHECK_MOCK['container'] = False
    with mock.patch('web.models.schain.SChainRecord'), \
            mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.monitor_sync_schain_container',
                       new=mock.Mock()) as sync:
        node_info = config.all()
        monitor_schain(skale, node_info, SCHAIN, ecdsa_sgx_key_name='test')
        args, kwargs = sync.call_args
        assert args[1] == SCHAIN
        assert args[2] == rotation_info['finish_ts']
