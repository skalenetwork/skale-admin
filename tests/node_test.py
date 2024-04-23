import os

import mock
import pytest

from skale import SkaleManager
from skale.utils.account_tools import generate_account, send_eth
from skale.utils.contracts_provision.main import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME
from skale.utils.helper import ip_from_bytes
from skale.wallets import Web3Wallet

from core.node import (
    get_block_device_size,
    get_node_hardware_info,
    Node, NodeExitStatus, NodeStatus
)
from core.node_config import NodeConfig
from tools.configs import NODE_DATA_PATH
from tools.configs.web3 import ABI_FILEPATH
from skale.utils.contracts_provision.main import (
    cleanup_nodes,
    link_nodes_to_validator,
)
from tests.utils import ENDPOINT, ETH_AMOUNT_PER_NODE

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture
def node(node_skales, skale, nodes):
    config = NodeConfig()
    node_index = 0
    config.id = nodes[node_index]
    node_data = skale.nodes.get(config.id)
    config.name = node_data['name']
    config.ip = ip_from_bytes(node_data['ip'])
    yield Node(node_skales[0], config)


@pytest.fixture
def new_node_wallet(skale):
    acc = generate_account(skale.web3)
    pk = acc['private_key']
    wallet = Web3Wallet(pk, skale.web3)
    send_eth(
        web3=skale.web3,
        wallet=skale.wallet,
        receiver_address=wallet.address,
        amount=ETH_AMOUNT_PER_NODE
    )
    return wallet


@pytest.fixture
def new_node_skale(skale, new_node_wallet):
    return SkaleManager(ENDPOINT, ABI_FILEPATH, new_node_wallet)


@pytest.fixture
def unregistered_node(skale, new_node_skale, validator):
    link_nodes_to_validator(skale, validator, [new_node_skale])
    config = NodeConfig()
    try:
        node = Node(new_node_skale, config)
        yield node
    finally:
        if node.config.id:
            cleanup_nodes(skale, [node.config.id])


def test_info_unregisted_node(unregistered_node):
    assert unregistered_node.info == {'status': 5}


def test_create_insufficient_funds(unregistered_node):
    ip = '1.1.1.2'
    public_ip = '2.2.2.3'
    port = 8081
    name = 'test-insuff'
    with mock.patch('core.node.check_required_balance',
                    new=mock.Mock(return_value=False)):
        res = unregistered_node.register(
            ip,
            public_ip,
            port,
            name,
            domain_name=DEFAULT_DOMAIN_NAME
        )
        assert res['status'] == 'error'
        assert res['errors'] == ['Insufficient funds, re-check your wallet']


def test_register_info(unregistered_node):
    unregistered_node.config.id = None
    ip, public_ip, port, name = generate_random_node_data()

    # Register new node and check that it successfully created on contracts
    with mock.patch('core.node.update_monitoring_services'):
        res = unregistered_node.register(
            ip,
            public_ip,
            port,
            name,
            domain_name=DEFAULT_DOMAIN_NAME
        )
    assert res['status'] == 'ok'
    res_data = res.get('data')

    skalepy_data = unregistered_node.skale.nodes.get_by_name(name)
    assert skalepy_data['name'] == name
    assert unregistered_node.skale.nodes.get(res_data['node_id'])
    assert res_data['node_id'] == unregistered_node.config.id

    # Register the same node again
    old_config_id = unregistered_node.config.id
    res = unregistered_node.register(
        ip,
        public_ip,
        port,
        name,
        domain_name=DEFAULT_DOMAIN_NAME
    )
    assert res['status'] == 'error'
    assert unregistered_node.config.id == old_config_id

    # Test info
    info = unregistered_node.info
    assert info['name'] == name
    assert info['ip'] == ip
    assert info['publicIP'] == public_ip
    assert info['port'] == int(port)
    assert info['id'] == unregistered_node.config.id
    assert info['publicKey'] == unregistered_node.skale.wallet.public_key
    assert info['status'] == 0


@pytest.fixture
def maintenance_node(skale, node):
    try:
        skale.nodes.set_node_in_maintenance(node.config.id)
        yield node
    finally:
        skale.nodes.remove_node_from_in_maintenance(node.config.id)


def test_get_node_id_node(node):
    node_id = node.get_node_id_from_contracts(
        node.config.name,
        node.config.ip
    )
    assert node_id == node.config.id


@pytest.fixture
def no_address_node(node):
    acc = generate_account(node.skale.web3)
    address = node.skale.wallet.address
    node.skale.wallet._address = acc['address']
    try:
        yield node
    finally:
        node.skale.wallet._address = address


def test_get_node_id_ignores_not_matched_address(no_address_node):
    nid = no_address_node.get_node_id_from_contracts(
        no_address_node.config.name, no_address_node.config.ip
    )
    assert nid == -1


@pytest.fixture
def no_id_node(node):
    no_id_config_path = os.path.join(NODE_DATA_PATH, 'no_id_config.json')
    config = NodeConfig(no_id_config_path)
    config.name = node.config.name
    config.sgx_key_name = node.config.sgx_key_name
    config.ip = node.config.ip
    config, node.config = node.config, config
    try:
        yield node
    finally:
        config, node.config = node.config, config


def test_get_node_id_restores_no_id_node(no_id_node):
    nid = no_id_node.get_node_id_from_contracts(
        no_id_node.config.name, no_id_node.config.ip
    )
    assert no_id_node.skale.nodes.get(nid)['name'] == no_id_node.config.name


def test_get_node_id_node_not_registered(unregistered_node):
    nid = unregistered_node.get_node_id_from_contracts(
        'undefined_name', '0.0.0.0')
    assert nid == -1


def test_start_exit(skale, node):
    skale.nodes.init_exit(node.config.id)
    node.exit({})
    status = NodeExitStatus(
        node.skale.nodes.get_node_status(node.config.id))

    assert status != NodeExitStatus.ACTIVE


def test_exit_status_active_forzen(skale, node):
    active_status_data = node.get_exit_status()
    assert list(active_status_data.keys()) == ['status', 'data', 'exit_time']
    assert active_status_data['status'] == NodeExitStatus.ACTIVE.name
    assert active_status_data['exit_time'] == 0

    skale.nodes.init_exit(node.config.id)
    node.exit({})
    exit_status_data = node.get_exit_status()
    assert list(exit_status_data.keys()) == ['status', 'data', 'exit_time']
    assert exit_status_data['status'] == NodeExitStatus.WAIT_FOR_ROTATIONS.name
    assert exit_status_data['exit_time'] != 0
    assert node.info['status'] == NodeStatus.FROZEN.value


def test_exit_status_maintenance(skale, maintenance_node):
    node_data = maintenance_node.get_exit_status()
    assert list(node_data.keys()) == ['status', 'data', 'exit_time']
    assert node_data['status'] == NodeExitStatus.IN_MAINTENANCE.name
    assert node_data['exit_time'] == 0


def test_node_maintenance(node, skale):
    res = node.set_maintenance_on()
    assert res == {'data': None, 'status': 'ok'}
    node_status = NodeStatus(
        skale.nodes.get_node_status(node.config.id))
    assert node_status == NodeStatus.IN_MAINTENANCE

    res = node.set_maintenance_off()
    assert res == {'data': None, 'status': 'ok'}
    node_status = NodeStatus(
        skale.nodes.get_node_status(node.config.id))
    assert node_status == NodeStatus.ACTIVE


def test_node_maintenance_error(node, skale):
    res = node.set_maintenance_off()
    assert res == {'status': 'error',
                   'errors': ['Node is not in maintenance mode']}
    try:
        res = node.set_maintenance_on()
        assert res == {'data': None, 'status': 'ok'}
        res = node.set_maintenance_on()
        assert res == {'status': 'error', 'errors': ['Node should be active']}
    finally:
        node.set_maintenance_off()


@mock.patch('core.node.get_block_device_size', return_value=300)
def test_get_node_hardware_info(get_block_device_size_mock):
    info = get_node_hardware_info()
    assert isinstance(info['cpu_total_cores'], int)
    assert isinstance(info['cpu_physical_cores'], int)
    assert info['cpu_physical_cores'] <= info['cpu_total_cores']
    assert isinstance(info['swap'], int)
    assert isinstance(info['memory'], int)
    assert isinstance(info['mem_used'], int)
    assert isinstance(info['mem_available'], int)
    assert isinstance(info['system_release'], str)
    assert isinstance(info['uname_version'], str)
    assert info['attached_storage_size'] == 300


def test_get_block_device_size():
    device = '/dev/test'
    size = 41224
    response_mock = mock.Mock()
    response_mock.json = mock.Mock(
        return_value={'Name': device, 'Size': size, 'Err': ''})
    with mock.patch('requests.get', return_value=response_mock):
        assert get_block_device_size() == size

    response_mock.json = mock.Mock(return_value={'Err': 'Test error'})
    with mock.patch('requests.get', return_value=response_mock):
        assert get_block_device_size() == -1
