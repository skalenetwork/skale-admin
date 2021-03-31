import os
import json
import time
from functools import partial
from pathlib import Path

import pytest
import mock

from skale.skale_manager import spawn_skale_manager_lib
from core.node_config import NodeConfig
from core.schains.creator import (check_schain_rotated,
                                  cleanup_schain_docker_entity,
                                  monitor_ima_container,
                                  monitor_schain,
                                  monitor_schain_container,
                                  monitor_sync_schain_container)
from core.schains.helper import get_schain_rotation_filepath
from core.schains.runner import get_container_name
from tests.utils import get_schain_contracts_data
from tools.configs.containers import IMA_CONTAINER, SCHAIN_CONTAINER
from tools.docker_utils import DockerUtils
from tools.helper import run_cmd
from web.models.schain import SChainRecord, upsert_schain_record
from core.schains.creator import get_monitor_mode, MonitorMode


# TODO: Add exited container test

@pytest.fixture
def node_config(skale):
    config = NodeConfig()
    config.id = 0
    config.sgx_key_name = 'test-sgx-key-name'
    config.ip = '127.0.0.1'
    return config


class ChecksMock:
    def __init__(self, schain_name: str, node_id: int, rotation_id=0):
        pass

    def get_all(self):
        return {
            'data_dir': True,
            'dkg': True,
            'config': True,
            'volume': True,
            'firewall_rules': True,
            'container': True,
            'exit_code_ok': True,
            'ima_container': True,
            'rpc': True,
            'blocks': True
        }

    def __getattr__(self, name):
        return True


class ChecksNoContainerMock(ChecksMock):
    @property
    def container(self):
        return False


def test_exiting_monitor(skale, node_config, db):
    rotation_info = {
        'in_progress': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time(),
        'rotation_id': 0
    }

    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)
    with mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
        mock.patch('core.schains.creator.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.creator.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain,
                       ecdsa_sgx_key_name=node_config.sgx_key_name)
        rotation.assert_called_with(schain_name=schain_name,
                                    timestamp=rotation_info['finish_ts'])


def test_rotating_monitor(skale, node_config, db):
    rotation_info = {
        'in_progress': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)

    def spawn_skale_lib_mock(skale):
        mocked_skale = spawn_skale_manager_lib(skale)
        mocked_skale.dkg.is_channel_opened = lambda x: True
        return mocked_skale

    with mock.patch('core.schains.creator.safe_run_dkg', return_value=True),\
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.generate_schain_config_with_skale',
                       new=mock.Mock(return_value=True)), \
            mock.patch('core.schains.creator.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.creator.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.spawn_skale_manager_lib',
                       spawn_skale_lib_mock), \
            mock.patch('core.schains.creator.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain, ecdsa_sgx_key_name='test')
        rotation.assert_called_with(schain_name=schain_name,
                                    timestamp=rotation_info['finish_ts'])


def test_new_schain_monitor(skale, node_config, db):
    rotation_info = {
        'in_progress': True,
        'new_schain': True,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)
    with mock.patch('core.schains.creator.run_dkg'), \
            mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.creator.SChainChecks', new=ChecksNoContainerMock), \
            mock.patch('core.schains.creator.get_rotation_state',
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
def cleanup_schain_container(dutils, schain_config):
    yield
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    dutils.safe_rm(get_container_name(SCHAIN_CONTAINER, schain_name),
                   force=True)


@pytest.fixture
def cleanup_ima_container(dutils, schain_config):
    yield
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    dutils.safe_rm(get_container_name(IMA_CONTAINER, schain_name),
                   force=True)


def test_monitor_sync_schain_container(skale, schain_config, dutils,
                                       cleanup_schain_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    start_ts = 0
    monitor_sync_schain_container(skale, schain,
                                  start_ts, volume_required=True,
                                  dutils=dutils)
    containers = dutils.get_all_schain_containers()
    assert len(containers) == 0

    monitor_sync_schain_container(skale, schain,
                                  start_ts,
                                  volume_required=False, dutils=dutils)
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'
    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' in inspection[0]['Args']
    cleanup_schain_docker_entity(schain_name)
    containers = dutils.get_all_schain_containers()
    assert len(containers) == 0


def test_monitor_ima_container(skale, schain_config, dutils,
                               cleanup_ima_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    monitor_ima_container(schain, dutils=dutils)
    containers = dutils.get_all_ima_containers()
    assert containers[0].name == f'skale_ima_{schain_name}'


def test_monitor_schain_container(skale, schain_config, dutils,
                                  cleanup_schain_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)

    monitor_schain_container(schain, volume_required=True)
    containers = dutils.get_all_schain_containers()
    assert len(containers) == 0

    monitor_schain_container(schain, volume_required=False)
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'

    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' not in inspection[0]['Args']
    cleanup_schain_docker_entity(schain_name)
    containers = dutils.get_all_schain_containers()
    assert len(containers) == 0


@pytest.mark.parametrize('in_progress,exiting_node,new_schain,mode',
                         [(False, False, False, MonitorMode.REGULAR),
                          (True, True, False, MonitorMode.EXIT),
                          (True, False, True, MonitorMode.SYNC)])
def test_get_monitor_mode_rotation(skale, schain_db,
                                   in_progress, exiting_node, new_schain, mode):
    schain_name = schain_db

    rotation_state = {
        'rotation_id': 0,
        'in_progress': in_progress,
        'exiting_node': exiting_node,
        'new_schain': new_schain,
        'finish_ts': 1
    }
    record = SChainRecord.get_by_name(schain_name)
    assert get_monitor_mode(record, rotation_state) == mode


def test_get_monitor_mode_repair(skale, schain_db):
    schain_name = schain_db

    rotation_state = {
        'rotation_id': 0,
        'in_progress': True,
        'exiting_node': True,
        'new_schain': False,
        'finish_ts': 1
    }
    record = SChainRecord.get_by_name(schain_name)
    record.set_repair_mode(True)
    assert get_monitor_mode(record, rotation_state) == MonitorMode.SYNC


@mock.patch('core.schains.creator.BACKUP_RUN', True)
def test_get_monitor_mode_backup_rotation(skale, schain_db):
    schain_name = schain_db

    rotation_state = {
        'rotation_id': 0,
        'in_progress': True,
        'exiting_node': True,
        'new_schain': False,
        'finish_ts': 1
    }
    record = SChainRecord.get_by_name(schain_name)
    assert get_monitor_mode(record, rotation_state) == MonitorMode.EXIT


@mock.patch('core.schains.creator.BACKUP_RUN', True)
def test_get_monitor_mode_backup_new_schain(skale, schain_db):
    schain_name = schain_db

    rotation_state = {
        'rotation_id': 0,
        'in_progress': False,
        'exiting_node': False,
        'new_schain': True
    }
    record = SChainRecord.get_by_name(schain_name)
    assert get_monitor_mode(record, rotation_state) == MonitorMode.REGULAR


@mock.patch('core.schains.creator.BACKUP_RUN', True)
def test_get_monitor_mode_backup_regular(skale, schain_db):
    schain_name = schain_db

    rotation_state = {
        'rotation_id': 0,
        'in_progress': False,
        'exiting_node': False,
        'new_schain': False
    }
    record = SChainRecord.get_by_name(schain_name)
    assert get_monitor_mode(record, rotation_state) == MonitorMode.REGULAR


@mock.patch('core.schains.creator.BACKUP_RUN', True)
def test_get_monitor_mode_backup_sync(skale, schain_db):
    schain_name = schain_db

    record = SChainRecord.get_by_name(schain_name)
    record.set_first_run(True)
    record.set_new_schain(False)

    rotation_state = {
        'rotation_id': 0,
        'in_progress': False,
        'exiting_node': False,
        'new_schain': False
    }
    record = SChainRecord.get_by_name(schain_name)
    assert get_monitor_mode(record, rotation_state) == MonitorMode.SYNC


def test_monitor_needs_reload(skale, node_config, db):
    rotation_info = {
        'in_progress': False,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }

    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)

    schain_record = upsert_schain_record(schain_name)

    schain_record.set_needs_reload(True)
    assert schain_record.needs_reload is True

    with mock.patch('core.schains.creator.CONTAINERS_DELAY', 0), \
        mock.patch('core.schains.creator.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.creator.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.creator.set_rotation_for_schain'), \
            mock.patch('core.schains.creator.monitor_schain_container'):
        node_info = node_config.all()
        monitor_schain(skale, node_info, schain,
                       ecdsa_sgx_key_name=node_config.sgx_key_name)
        schain_record = upsert_schain_record(schain_name)
        assert schain_record.needs_reload is False
