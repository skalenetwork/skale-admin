import json
import os
import time
from functools import partial
from pathlib import Path

import pytest
import mock

from core.node_config import NodeConfig
from core.schains.creator import monitor_schain, check_schain_rotated, repair_schain
from core.schains.helper import get_schain_rotation_filepath
from core.schains.runner import get_container_name
from tools.configs.containers import SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import run_cmd


# TODO: Add exited container test

@pytest.fixture
def node_config(skale):
    config = NodeConfig()
    config.id = 0
    config.sgx_key_name = 'test-sgx-key-name'
    config.ip = '127.0.0.1'
    return config


def get_schain_contracts_data():
    """ Schain data mock in case if schain on contracts is not required """
    return {
        'name': 'test',
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


def test_exiting_monitor(skale, node_config, db):
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time(),
        'rotation_id': 0
    }

    schain = get_schain_contracts_data()
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('core.schains.creator.CONTAINERS_DELAY', 0),\
        mock.patch('core.schains.creator.SChainChecks.run_checks'), \
        mock.patch('core.schains.creator.SChainChecks.get_all',
                   new=mock.Mock(return_value=CHECK_MOCK)),\
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain,
                       ecdsa_sgx_key_name=node_config.sgx_key_name)
        rotation.assert_called_with(schain, rotation_info['finish_ts'])


def test_rotating_monitor(skale, node_config, db):
    rotation_info = {
        'result': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    schain = get_schain_contracts_data()
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    with mock.patch('core.schains.creator.run_dkg'),\
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.generate_schain_config_with_skale',
                       new=mock.Mock(return_value=True)), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain, ecdsa_sgx_key_name='test')
        rotation.assert_called_with(schain, rotation_info['finish_ts'])


def test_new_schain_monitor(skale, node_config, db):
    rotation_info = {
        'result': True,
        'new_schain': True,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    CHECK_MOCK['rotation_in_progress'] = rotation_info
    CHECK_MOCK['container'] = False
    schain = get_schain_contracts_data()
    with mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks.run_checks'), \
            mock.patch('core.schains.creator.SChainChecks.get_all',
                       new=mock.Mock(return_value=CHECK_MOCK)), \
            mock.patch('core.schains.creator.check_for_rotation',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.monitor_sync_schain_container',
                       new=mock.Mock()) as sync:
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain, ecdsa_sgx_key_name='test')
        args, kwargs = sync.call_args
        assert args[1] == schain
        assert args[2] == rotation_info['finish_ts']


def test_check_schain_rotated(skale, schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    assert not check_schain_rotated(schain_name)
    info_mock = {
        'status': 'exited',
        'stats': {
            'State': {
                'ExitCode': 0
            }
        }
    }
    with mock.patch('core.schains.creator.DockerUtils.get_info',
                    new=mock.Mock(return_value=info_mock)):
        assert not check_schain_rotated(schain_name)
        path = get_schain_rotation_filepath(schain_name)
        Path(path).touch()
        assert check_schain_rotated(schain_name)
        os.remove(path)


@pytest.fixture
def dutils():
    c = DockerUtils(volume_driver='local')
    c.run_container = partial(c.run_container)
    return c


@pytest.fixture
def cleanup_container(dutils):
    yield
    schain = get_schain_contracts_data()
    dutils.safe_rm(get_container_name(SCHAIN_CONTAINER, schain['name']),
                   force=True)


@pytest.mark.parametrize(
    'container_check,volume_check',
    [(False, False), (True, False), (False, True), (True, True)]
)
def test_repair_schain(skale, schain_config, dutils, cleanup_container,
                       container_check, volume_check):
    # sids = skale.schains_internal.get_all_schains_ids()
    # names = [skale.schains.get(sid)['name'] for sid in sids]
    # print(names)

    schain = get_schain_contracts_data()
    schain_name = schain['name']
    checks = {'container': True, 'volume': True}
    start_ts = 0
    rotation_id = 0
    repair_schain(skale, schain, checks, start_ts, rotation_id, dutils=dutils)
    schains = dutils.get_all_schain_containers()
    assert schains[0].name == f'skale_schain_{schain_name}'
    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' in inspection[0]['Args']
