import os

import mock
import pytest

from skale.utils.contracts_provision.main import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME

from core.node import Node, NodeExitStatuses, NodeStatuses
from core.node_config import NodeConfig

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
    domain_name = 'test'
    with mock.patch('core.node.check_required_balance',
                    new=mock.Mock(return_value=False)):
        res = node.register(ip, public_ip, port, name, domain_name)
        assert res['status'] == 0
        assert res['errors'] == ['Insufficient funds, re-check your wallet']


def test_register_info(node):
    node.config.id = None
    ip, public_ip, port, name = generate_random_node_data()

    # Register new node and check that it successfully created on contracts
    with mock.patch('core.node.run_filebeat_service'):
        res = node.register(ip, public_ip, port, name,
                            domain_name=DEFAULT_DOMAIN_NAME)
    assert res['status'] == 1
    res_data = res.get('data')

    skalepy_data = node.skale.nodes.get_by_name(name)
    assert skalepy_data['name'] == name
    assert node.skale.nodes.get(res_data['node_id'])
    assert res_data['node_id'] == node.config.id

    # Register the same node again
    old_config_id = node.config.id
    res = node.register(ip, public_ip, port, name,
                        domain_name=DEFAULT_DOMAIN_NAME)
    assert res['status'] == 0
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
    config.id = skale.nodes.node_name_to_index(name)
    yield Node(skale, config)


def test_start_exit(active_node):
    active_node.exit({})
    status = NodeExitStatuses(active_node.skale.nodes.get_node_status(active_node.config.id))

    assert status != NodeExitStatuses.ACTIVE


def test_exit_status(active_node):
    active_status_data = active_node.get_exit_status()
    assert list(active_status_data.keys()) == ['status', 'data', 'exit_time']
    assert active_status_data['status'] == NodeExitStatuses.ACTIVE.name
    assert active_status_data['exit_time'] == 0

    active_node.exit({})
    exit_status_data = active_node.get_exit_status()
    assert list(exit_status_data.keys()) == ['status', 'data', 'exit_time']
    assert exit_status_data['status'] == NodeExitStatuses.WAIT_FOR_ROTATIONS.name
    assert exit_status_data['exit_time'] != 0
    assert active_node.info['status'] == NodeStatuses.FROZEN.value


def test_node_maintenance(active_node, skale):
    res = active_node.set_maintenance_on()
    node_status = NodeStatuses(skale.nodes.get_node_status(active_node.config.id))
    assert res == {'status': 0}
    assert node_status == NodeStatuses.IN_MAINTENANCE

    res = active_node.set_maintenance_off()
    node_status = NodeStatuses(skale.nodes.get_node_status(active_node.config.id))
    assert res == {'status': 0}
    assert node_status == NodeStatuses.ACTIVE


def test_node_maintenance_error(active_node, skale):
    res = active_node.set_maintenance_off()
    assert res == {'status': 1, 'errors': ['Node is not in maintenance mode']}

    active_node.set_maintenance_on()
    res = active_node.set_maintenance_on()
    assert res == {'status': 1, 'errors': ['Node should be active']}
