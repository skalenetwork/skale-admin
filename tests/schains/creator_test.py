import os
import json
import time
from pathlib import Path

import mock
import pytest
import requests

from core.node_config import NodeConfig
from core.schains.monitor import (check_schain_rotated,
                                  cleanup_schain_docker_entity,
                                  monitor_ima_container,
                                  monitor_schain,
                                  monitor_schain_container,
                                  monitor_sync_schain_container, monitor_ima)
from core.schains.helper import get_schain_rotation_filepath
from core.schains.runner import get_container_name
from tests.utils import get_schain_contracts_data
from tools.configs.containers import (
    IMA_CONTAINER,
    MAX_SCHAIN_RESTART_COUNT,
    SCHAIN_CONTAINER
)
from tools.helper import run_cmd
from web.models.schain import SChainRecord, upsert_schain_record
from core.schains.monitor import get_monitor_mode, MonitorMode

from tools.helper import read_json
from tools.configs.ima import SCHAIN_IMA_ABI_FILEPATH

# TODO: Add exited container test


@pytest.fixture
def node_config(skale):
    config = NodeConfig()
    config.id = 0
    config.sgx_key_name = 'test-sgx-key-name'
    config.ip = '127.0.0.1'
    return config


class ChecksMock:
    def __init__(self, schain_name: str, node_id: int, rotation_id=0, dutils=None):
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


def test_exiting_monitor(skale, skale_ima, node_config, db, dutils):
    rotation_info = {
        'in_progress': True,
        'new_schain': True,
        'exiting_node': True,
        'finish_ts': time.time(),
        'rotation_id': 0
    }

    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)
    with mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0), \
        mock.patch('core.schains.monitor.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.monitor.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.monitor.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(
            skale, skale_ima, node_info, schain,
            ecdsa_sgx_key_name=node_config.sgx_key_name,
            dutils=dutils)
        rotation.assert_called_with(schain_name=schain_name,
                                    timestamp=rotation_info['finish_ts'])


def test_rotating_monitor(skale, skale_ima, node_config, db, dutils):
    rotation_info = {
        'in_progress': True,
        'new_schain': False,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)

    with mock.patch('core.schains.monitor.safe_run_dkg', return_value=True),\
            mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.monitor.init_schain_config',
                       new=mock.Mock(return_value=True)), \
            mock.patch('core.schains.monitor.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.monitor.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.monitor.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch.object(skale.dkg, 'is_channel_opened', return_value=True), \
            mock.patch('core.schains.monitor.set_rotation_for_schain') as rotation:
        node_info = node_config.all()
        monitor_schain(skale, skale_ima, node_info,
                       schain, ecdsa_sgx_key_name='test', dutils=dutils)
        rotation.assert_called_with(schain_name=schain_name,
                                    timestamp=rotation_info['finish_ts'])


def test_new_schain_monitor(skale, skale_ima, node_config, db, dutils):
    rotation_info = {
        'in_progress': True,
        'new_schain': True,
        'exiting_node': False,
        'finish_ts': time.time(),
        'rotation_id': 0
    }
    schain_name = 'test'
    schain = get_schain_contracts_data(schain_name=schain_name)
    with mock.patch('core.schains.monitor.run_dkg'), \
            mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0), \
            mock.patch('core.schains.monitor.SChainChecks', new=ChecksNoContainerMock), \
            mock.patch('core.schains.monitor.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.monitor.monitor_sync_schain_container',
                       new=mock.Mock()) as sync:
        node_info = node_config.all()
        monitor_schain(skale, skale_ima, node_info,
                       schain, ecdsa_sgx_key_name='test', dutils=dutils)
        args, kwargs = sync.call_args
        assert args[1] == schain
        assert args[2] == rotation_info['finish_ts']


def test_check_schain_rotated(skale, schain_config, dutils):

    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    assert not check_schain_rotated(schain_name, dutils)
    info_mock = {
        'status': 'exited',
        'stats': {
            'State': {
                'ExitCode': 0
            }
        }
    }
    dutils.get_info = mock.Mock(return_value=info_mock)
    assert not check_schain_rotated(schain_name, dutils=dutils)
    path = get_schain_rotation_filepath(schain_name)
    Path(path).touch()
    assert check_schain_rotated(schain_name, dutils=dutils)
    os.remove(path)


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


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
def test_monitor_sync_schain_container(
    get_image,
    skale,
    schain_config,
    dutils,
    cleanup_schain_container,
    cert_key_pair,
    schain_db,
    skaled_mock_image
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    start_ts = 0
    record = SChainRecord.get_by_name(schain_name)
    record.set_restart_count(2)
    monitor_sync_schain_container(
        skale,
        schain,
        start_ts,
        schain_record=record,
        volume_required=True,
        dutils=dutils
    )
    containers = dutils.get_all_schain_containers(all=True)
    assert len(containers) == 0

    monitor_sync_schain_container(
        skale,
        schain,
        start_ts,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'
    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' in inspection[0]['Args']
    assert record.restart_count == 0
    cleanup_schain_docker_entity(schain_name, dutils=dutils)
    containers = dutils.get_all_schain_containers()
    assert len(containers) == 0


def test_monitor_ima_container(skale, schain_config, dutils,
                               cleanup_ima_container):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    mainnet_chain_id = skale.web3.eth.chainId
    monitor_ima_container(
        schain,
        mainnet_chain_id=mainnet_chain_id,
        dutils=dutils
    )
    containers = dutils.get_all_ima_containers()
    assert containers[0].name == f'skale_ima_{schain_name}'


def kill_schain_with_code(exit_code):
    requests.post('http://127.0.0.1:10003', json={'exit_code': exit_code})


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
@pytest.mark.parametrize('exit_code,eventual_result',
                         [(1, 'running'),
                          (200, 'exited'),
                          (0, 'exited')])
def test_monitor_schain_container_exit_code(
    get_image,
    skale,
    schain_config,
    dutils,
    cleanup_schain_container,
    cert_key_pair,
    schain_db,
    skaled_mock_image,
    exit_code,
    eventual_result
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    record = SChainRecord.get_by_name(schain_name)

    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'running'

    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' not in inspection[0]['Args']

    time.sleep(2)
    kill_schain_with_code(exit_code)
    time.sleep(2)
    containers = dutils.get_all_schain_containers(all=True)

    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'exited'
    dutils.container_exit_code(containers[0].name) == exit_code

    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    time.sleep(2)

    containers = dutils.get_all_schain_containers(all=True)
    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == eventual_result
    if exit_code != 1:
        dutils.container_exit_code(containers[0].name) == exit_code

    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' not in inspection[0]['Args']


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
def test_monitor_maximum_restart_count(
    get_image,
    skale,
    schain_config,
    dutils,
    cleanup_schain_container,
    cert_key_pair,
    schain_db,
    skaled_mock_image
):

    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    record = SChainRecord.get_by_name(schain_name)
    record.set_restart_count(MAX_SCHAIN_RESTART_COUNT)
    exit_code = 1

    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'running'
    assert record.restart_count == 0

    record.set_restart_count(MAX_SCHAIN_RESTART_COUNT + 1)

    time.sleep(2)
    kill_schain_with_code(exit_code)
    time.sleep(2)
    containers = dutils.get_all_schain_containers(all=True)

    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'exited'
    dutils.container_exit_code(containers[0].name) == exit_code

    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    time.sleep(2)

    containers = dutils.get_all_schain_containers(all=True)
    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'exited'
    dutils.container_exit_code(containers[0].name) == exit_code


@mock.patch(
    'core.schains.runner.get_image_name',
    return_value='skaled-mock'
)
def test_monitor_schain_container_cleanup_entity(
    get_image,
    skale,
    schain_config,
    dutils,
    cleanup_schain_container,
    cert_key_pair,
    schain_db,
    skaled_mock_image
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain = get_schain_contracts_data(schain_name=schain_name)
    record = SChainRecord.get_by_name(schain_name)
    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=True,
        dutils=dutils
    )
    time.sleep(4)
    containers = dutils.get_all_schain_containers(all=True)
    assert len(containers) == 0

    monitor_schain_container(
        schain,
        schain_record=record,
        volume_required=False,
        dutils=dutils
    )
    containers = dutils.get_all_schain_containers()
    assert containers[0].name == f'skale_schain_{schain_name}'
    assert containers[0].status == 'running'

    res = run_cmd(['docker', 'inspect', f'skale_schain_{schain_name}'])
    inspection = json.loads(res.stdout.decode('utf-8'))
    assert '--download-snapshot' not in inspection[0]['Args']

    cleanup_schain_docker_entity(schain_name, dutils=dutils)
    containers = dutils.get_all_schain_containers(all=True)
    assert len(containers) == 0


@pytest.mark.parametrize('in_progress,exiting_node,new_schain,mode',
                         [(False, False, False, MonitorMode.REGULAR),
                          (True, True, False, MonitorMode.EXIT),
                          (True, False, True, MonitorMode.SYNC)])
def test_get_monitor_mode_rotation(
    get_image,
    skale,
    schain_db,
    in_progress,
    exiting_node,
    new_schain,
    mode
):
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


@mock.patch('core.schains.monitor.BACKUP_RUN', True)
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


@mock.patch('core.schains.monitor.BACKUP_RUN', True)
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


@mock.patch('core.schains.monitor.BACKUP_RUN', True)
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


@mock.patch('core.schains.monitor.BACKUP_RUN', True)
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


def test_monitor_ima(skale_ima, schain_on_contracts, schain_config, dutils):
    schain_name = schain_on_contracts
    schain = get_schain_contracts_data(schain_name=schain_name)
    monitor_ima(skale_ima, schain, mainnet_chain_id=1, dutils=dutils)
    containers = dutils.get_all_ima_containers()
    assert len(containers) == 0

    schain_ima_abi = read_json(SCHAIN_IMA_ABI_FILEPATH)
    skale_ima.linker.connect_schain(
        schain_name,
        [
            schain_ima_abi['community_locker_address'],
            schain_ima_abi['token_manager_eth_address'],
            schain_ima_abi['token_manager_erc20_address'],
            schain_ima_abi['token_manager_erc721_address'],
            schain_ima_abi['token_manager_erc1155_address']
        ]
    )
    with mock.patch('core.schains.monitor.copy_schain_ima_abi', return_value=True):
        monitor_ima(skale_ima, schain, mainnet_chain_id=1, dutils=dutils)
        containers = dutils.get_all_ima_containers()
        assert containers[0].name == f'skale_ima_{schain_name}'


def test_monitor_needs_reload(skale, skale_ima, node_config, db, dutils):
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

    with mock.patch('core.schains.monitor.CONTAINERS_DELAY', 0), \
        mock.patch('core.schains.monitor.SChainChecks', new=ChecksMock), \
            mock.patch('core.schains.monitor.get_rotation_state',
                       new=mock.Mock(return_value=rotation_info)), \
            mock.patch('core.schains.monitor.set_rotation_for_schain'), \
            mock.patch('core.schains.monitor.monitor_schain_container'):
        node_info = node_config.all()
        monitor_schain(skale, skale_ima, node_info, schain,
                       ecdsa_sgx_key_name=node_config.sgx_key_name, dutils=dutils)
        schain_record = upsert_schain_record(schain_name)
        assert schain_record.needs_reload is False
