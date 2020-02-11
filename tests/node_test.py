import os

import mock
import pytest

from core.node import Node, NodeExitStatuses
from core.node_config import NodeConfig

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


NODE_NAME = 'test'


@pytest.fixture
def node(skale):
    config = NodeConfig()
    yield Node(skale, config)


def test_info_unregisted_node(node):
    assert node.info == {'status': 0}


def test_create_insufficient_funds(node):
    ip = '1.1.1.2'
    public_ip = '2.2.2.3'
    port = 8081
    name = 'test-insuff'
    with mock.patch('core.node.check_required_balance',
                    new=mock.Mock(return_value=False)):
        res = node.register(ip, public_ip, port, name)
        assert res['status'] == 0
        assert res['errors'] == ['Insufficient funds, re-check your wallet']


def test_register_info(node):
    ip = '1.1.1.1'
    public_ip = '2.2.2.2'
    port = 8080

    # Register new node and check that it successfully created on contracts
    with mock.patch('core.node.run_filebeat_service'):
        res = node.register(ip, public_ip, port, NODE_NAME)
    assert res['status'] == 1
    res_data = res.get('data')

    skalepy_data = node.skale.nodes_data.get_by_name(NODE_NAME)
    assert skalepy_data['name'] == 'test'
    assert node.skale.nodes_data.get(res_data['node_id'])
    assert res_data['node_id'] == node.config.id

    # Register the same node again
    old_config_id = node.config.id
    res = node.register(ip, public_ip, port, NODE_NAME)
    assert res['status'] == 0
    assert node.config.id == old_config_id

    # Test info
    info = node.info
    assert info['name'] == NODE_NAME
    assert info['ip'] == ip
    assert info['publicIP'] == public_ip
    assert info['port'] == int(port)
    assert info['id'] == node.config.id
    assert info['publicKey'] == node.skale.wallet.public_key


def test_start_exit(node):
    node.exit({})
    status = NodeExitStatuses(node.skale.nodes_data.get_node_status(node.config.id))

    assert status != NodeExitStatuses.ACTIVE
