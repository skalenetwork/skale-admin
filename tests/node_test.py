import os

import mock
import pytest

from skale.transactions.result import RevertError
from skale.utils.contracts_provision.main import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.node import (
    get_attached_storage_block_device,
    get_block_device_size,
    get_node_hardware_info,
    Node, NodeExitStatus, NodeStatus
)
from core.node_config import NodeConfig
from tools.configs.resource_allocation import DISK_MOUNTPOINT_FILEPATH

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture
def node(skale):
    config = NodeConfig()
    yield Node(skale, config)


def test_info_unregisted_node(node):
    assert node.info == {'status': 5}


def test_create_insufficient_funds(node):
    ip = '1.1.1.2'
    public_ip = '2.2.2.3'
    port = 8081
    name = 'test-insuff'
    with mock.patch('core.node.check_required_balance',
                    new=mock.Mock(return_value=False)):
        res = node.register(
            ip, public_ip, port, name, domain_name=DEFAULT_DOMAIN_NAME)
        assert res['status'] == 'error'
        assert res['errors'] == ['Insufficient funds, re-check your wallet']


def test_register_info(node):
    node.config.id = None
    ip, public_ip, port, name = generate_random_node_data()

    # Register new node and check that it successfully created on contracts
    with mock.patch('core.node.run_filebeat_service'):
        res = node.register(ip, public_ip, port, name,
                            domain_name=DEFAULT_DOMAIN_NAME)
    assert res['status'] == 'ok'
    res_data = res.get('data')

    skalepy_data = node.skale.nodes.get_by_name(name)
    assert skalepy_data['name'] == name
    assert node.skale.nodes.get(res_data['node_id'])
    assert res_data['node_id'] == node.config.id

    # Register the same node again
    old_config_id = node.config.id
    res = node.register(ip, public_ip, port, name, domain_name=DEFAULT_DOMAIN_NAME)
    assert res['status'] == 'error'
    assert node.config.id == old_config_id

    # Test info
    info = node.info
    assert info['name'] == name
    assert info['ip'] == ip
    assert info['publicIP'] == public_ip
    assert info['port'] == int(port)
    assert info['id'] == node.config.id
    assert info['publicKey'] == node.skale.wallet.public_key
    assert info['status'] == 0


@pytest.fixture
def active_node(skale):
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(
        ip=ip,
        port=port,
        name=name,
        public_ip=public_ip,
        domain_name=DEFAULT_DOMAIN_NAME,
        wait_for=True
    )
    config = NodeConfig()
    node_id = skale.nodes.node_name_to_index(name)
    config.id = node_id
    config.ip = ip
    config.name = name
    yield Node(skale, config)
    status = skale.nodes.get_node_status(node_id)
    if status not in (NodeStatus.FROZEN.value, NodeStatus.FROZEN.value):
        if skale.nodes.get_node_status(node_id) == \
                NodeStatus.IN_MAINTENANCE.value:
            skale.nodes.remove_node_from_in_maintenance(node_id)
        skale.manager.node_exit(node_id)


def test_get_config_data_active_node(active_node):
    node_id = active_node.get_node_id_from_contracts(
        active_node.config.name, active_node.config.ip
    )
    assert node_id == active_node.config.id


@pytest.fixture
def broken_node(skale):
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)
    node_id = skale.nodes.node_name_to_index(name)
    config = NodeConfig()
    config.name = name
    config.ip = ip
    yield Node(skale, config)
    skale.manager.node_exit(node_id)


def test_get_config_data_broken_node(broken_node):
    nid = broken_node.get_node_id_from_contracts(
        broken_node.config.name, broken_node.config.ip
    )
    assert broken_node.skale.nodes.get(nid)['name'] == broken_node.config.name


@pytest.fixture
def not_registered_node(skale):
    config = NodeConfig()
    return Node(skale, config)


def test_get_config_data_node_not_registered(not_registered_node):
    nid = not_registered_node.get_node_id_from_contracts(
        'undefined_name', '0.0.0.0')
    assert nid == -1


def test_start_exit(active_node):
    active_node.exit({})
    status = NodeExitStatus(
        active_node.skale.nodes.get_node_status(active_node.config.id))

    assert status != NodeExitStatus.ACTIVE


def test_exit_status(active_node):
    active_status_data = active_node.get_exit_status()
    assert list(active_status_data.keys()) == ['status', 'data', 'exit_time']
    assert active_status_data['status'] == NodeExitStatus.ACTIVE.name
    assert active_status_data['exit_time'] == 0

    active_node.exit({})
    exit_status_data = active_node.get_exit_status()
    assert list(exit_status_data.keys()) == ['status', 'data', 'exit_time']
    assert exit_status_data['status'] == NodeExitStatus.WAIT_FOR_ROTATIONS.name
    assert exit_status_data['exit_time'] != 0
    assert active_node.info['status'] == NodeStatus.FROZEN.value


def test_node_maintenance(active_node, skale):
    res = active_node.set_maintenance_on()
    assert res == {'data': None, 'status': 'ok'}
    node_status = NodeStatus(
        skale.nodes.get_node_status(active_node.config.id))
    assert node_status == NodeStatus.IN_MAINTENANCE

    res = active_node.set_maintenance_off()
    assert res == {'data': None, 'status': 'ok'}
    node_status = NodeStatus(
        skale.nodes.get_node_status(active_node.config.id))
    assert node_status == NodeStatus.ACTIVE


def test_node_maintenance_error(active_node, skale):
    res = active_node.set_maintenance_off()
    assert res == {'status': 'error',
                   'errors': ['Node is not in maintenance mode']}

    res = active_node.set_maintenance_on()
    assert res == {'data': None, 'status': 'ok'}
    with pytest.raises(RevertError):
        res = active_node.set_maintenance_on()


@pytest.fixture
def block_device_file():
    device = '/dev/xvdd'
    with open(DISK_MOUNTPOINT_FILEPATH, 'w') as dm_file:
        dm_file.write(device)
    yield DISK_MOUNTPOINT_FILEPATH
    os.remove(DISK_MOUNTPOINT_FILEPATH)


@mock.patch('core.node.get_block_device_size', return_value=300)
def test_get_node_hardware_info(get_block_device_size_mock, block_device_file):
    info = get_node_hardware_info()
    assert isinstance(info['cpu_total_cores'], int)
    assert isinstance(info['cpu_physical_cores'], int)
    assert info['cpu_physical_cores'] <= info['cpu_total_cores']
    assert isinstance(info['swap'], int)
    assert isinstance(info['memory'], int)
    assert isinstance(info['system_release'], str)
    assert isinstance(info['uname_version'], str)
    assert info['attached_storage_size'] == 300


def test_get_attached_storage_block_device(block_device_file) -> int:
    assert get_attached_storage_block_device() == '/dev/xvdd'


def test_get_block_device_size():
    device = '/dev/test'
    size = 41224
    response_mock = mock.Mock()
    response_mock.json = mock.Mock(
        return_value={'Name': device, 'Size': size, 'Err': ''})
    with mock.patch('requests.get', return_value=response_mock):
        assert get_block_device_size(device) == size

    response_mock.json = mock.Mock(return_value={'Err': 'Test error'})
    with mock.patch('requests.get', return_value=response_mock):
        assert get_block_device_size(device) == -1
