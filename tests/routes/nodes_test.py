import pytest
from mock import patch

from flask import Flask
from web3 import Web3


from tools.docker_utils import DockerUtils
from core.node import Node
from core.node_config import NodeConfig
from tests.utils import get_bp_data, post_bp_data
from web.routes.nodes import construct_nodes_bp

from skale.utils.contracts_provision.utils import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME


@pytest.fixture
def node_config(skale):
    return NodeConfig()


@pytest.fixture
def node(skale, node_config):
    node = Node(skale, node_config)
    return node


@pytest.fixture
def skale_bp(skale, node):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_nodes_bp(skale, node, dutils))
    return app.test_client()


def test_check_node_name(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': 'test'})
    assert data == {'status': 'ok', 'payload': {'name_available': True}}
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, domain_name=DEFAULT_DOMAIN_NAME, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': name})
    assert data == {'status': 'ok', 'payload': {'name_available': False}}
    node_idx = skale.nodes.node_name_to_index(name)
    skale.manager.node_exit(node_idx, wait_for=True)


def test_check_node_ip(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': '0.0.0.0'})
    assert data == {'status': 'ok', 'payload': {'ip_available': True}}
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, domain_name=DEFAULT_DOMAIN_NAME, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': ip})
    assert data == {'status': 'ok', 'payload': {'ip_available': False}}
    node_idx = skale.nodes.node_name_to_index(name)
    skale.manager.node_exit(node_idx, wait_for=True)


def test_containers_list(skale_bp, skale):
    dutils = DockerUtils(volume_driver='local')
    data = get_bp_data(skale_bp, '/containers/list')
    expected = {
        'status': 'ok',
        'payload': {
            'containers': dutils.get_all_skale_containers(format=True)
        }
    }
    assert data == expected
    data = get_bp_data(skale_bp, '/containers/list', {'all': True})
    expected = {'status': 'ok',
                'payload': {
                    'containers': dutils.get_all_skale_containers(all=True,
                                                                  format=True)}
                }
    assert data == expected


def test_node_info(skale_bp, node):
    data = get_bp_data(skale_bp, '/node-info')
    assert data == {'status': 'ok', 'payload': {'node_info': node.info}}


def register_mock(self, ip, public_ip, port, name, gas_limit=None,
                  gas_price=None, skip_dry_run=False):
    return {'status': 1, 'data': 1}


def set_maintenance_mock(self):
    return {'status': 0}


@patch.object(Node, 'register', register_mock)
def test_node_create(skale_bp, node_config):
    ip, public_ip, port, name = generate_random_node_data()
    # Test with gas_limit and gas_price
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_limit': 8000000,
        'gas_price': 2 * 10 ** 9
    }
    data = post_bp_data(skale_bp, '/create-node', json_data)
    assert data == {'status': 'ok', 'payload': {'node_data': 1}}

    # Without gas_limit
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_price': 2 * 10 ** 9
    }
    data = post_bp_data(skale_bp, '/create-node', json_data)
    assert data == {'status': 'ok', 'payload': {'node_data': 1}}

    # Without gas_limit and gas_price
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_price': 2 * 10 ** 9
    }
    data = post_bp_data(skale_bp, '/create-node', json_data)
    assert data == {'status': 'ok', 'payload': {'node_data': 1}}


def failed_register_mock(
    self, ip, public_ip, port, name, gas_limit=None,
    gas_price=None, skip_dry_run=False
):
    return {'status': 0, 'errors': ['Already registered']}


@patch.object(Node, 'register', failed_register_mock)
def test_create_with_errors(skale_bp, node_config):
    ip, public_ip, port, name = generate_random_node_data()
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port
    }
    data = post_bp_data(skale_bp, '/create-node', json_data)
    assert data == {'payload': ['Already registered'], 'status': 'error'}


def get_expected_signature(skale, validator_id):
    unsigned_hash = Web3.soliditySha3(['uint256'], [validator_id])
    signed_hash = skale.wallet.sign_hash(unsigned_hash.hex())
    return signed_hash.signature.hex()


def test_node_signature(skale_bp, skale):
    validator_id = 1
    json_data = {'validator_id': validator_id}
    data = get_bp_data(skale_bp, 'node-signature', json_data)
    expected_signature = get_expected_signature(skale, validator_id)
    assert data == {'status': 'ok', 'payload': {
        'signature': expected_signature}}


@patch.object(Node, 'set_maintenance_on', set_maintenance_mock)
def test_set_maintenance_on(skale_bp, skale, node_config):
    data = post_bp_data(skale_bp, '/api/node/maintenance-on')
    assert data == {'payload': {}, 'status': 'ok'}


@patch.object(Node, 'set_maintenance_off', set_maintenance_mock)
def test_set_maintenance_off(skale_bp, skale, node_config):
    data = post_bp_data(skale_bp, '/api/node/maintenance-off')
    assert data == {'payload': {}, 'status': 'ok'}
