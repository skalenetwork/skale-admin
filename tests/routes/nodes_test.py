import pytest
from mock import patch

from flask import Flask, appcontext_pushed, g
from web3 import Web3


from tools.docker_utils import DockerUtils
from core.node import Node, NodeStatus
from core.node_config import NodeConfig
from tests.utils import get_bp_data, post_bp_data
from web.routes.nodes import construct_nodes_bp

from skale.utils.contracts_provision.utils import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME
from skale.utils.helper import ip_from_bytes


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_nodes_bp())

    def handler(sender, **kwargs):
        g.docker_utils = DockerUtils(volume_driver='local')
        g.wallet = skale.wallet
        g.config = NodeConfig()

    with appcontext_pushed.connected_to(handler, app):
        yield app.test_client()


@pytest.fixture
def node_contracts(skale):
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name,
                              domain_name=DEFAULT_DOMAIN_NAME, wait_for=True)
    node_id = skale.nodes.node_name_to_index(name)
    yield node_id
    skale.manager.node_exit(node_id, wait_for=True)


@pytest.fixture
def node_config():
    return NodeConfig()


def test_check_node_name(skale_bp, skale, node_contracts):
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': 'test'})
    assert data == {'status': 'ok', 'payload': {'name_available': True}}
    node_id = node_contracts
    name = skale.nodes.get(node_id)['name']
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': name})
    assert data == {'status': 'ok', 'payload': {'name_available': False}}


def test_check_node_ip(skale_bp, skale, node_contracts):
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': '0.0.0.0'})
    assert data == {'status': 'ok', 'payload': {'ip_available': True}}
    node_id = node_contracts
    ip = ip_from_bytes(skale.nodes.get(node_id)['ip'])
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': ip})
    assert data == {'status': 'ok', 'payload': {'ip_available': False}}


def test_containers_list(skale_bp):
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


def test_node_info(skale_bp, skale, node_contracts, node_config):
    node_id = node_contracts
    node_config.id = node_id
    data = get_bp_data(skale_bp, '/node-info')
    status = NodeStatus.ACTIVE.value
    assert data['status'] == 'ok'
    node_info = data['payload']['node_info']
    assert node_info['id'] == node_id
    assert node_info['status'] == status
    assert node_info['owner'] == skale.wallet.address


def register_mock(self, ip, public_ip, port, name, domain_name, gas_limit=None,
                  gas_price=None, skip_dry_run=False):
    return {'status': 1, 'data': 1}


def set_maintenance_mock(self):
    return {'status': 0}


def set_domain_name_mock(self, data):
    return {'status': 0}


@patch.object(Node, 'register', register_mock)
def test_node_create(skale_bp):
    ip, public_ip, port, name = generate_random_node_data()
    # Test with gas_limit and gas_price
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_limit': 8000000,
        'gas_price': 2 * 10 ** 9,
        'domain_name': DEFAULT_DOMAIN_NAME
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
    self, ip, public_ip, port, name, domain_name, gas_limit=None,
    gas_price=None, skip_dry_run=False
):
    return {'status': 0, 'errors': ['Already registered']}


@patch.object(Node, 'register', failed_register_mock)
def test_create_with_errors(skale_bp):
    ip, public_ip, port, name = generate_random_node_data()
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'domain_name': DEFAULT_DOMAIN_NAME
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
def test_set_maintenance_on(skale_bp, skale):
    data = post_bp_data(skale_bp, '/api/node/maintenance-on')
    assert data == {'payload': {}, 'status': 'ok'}


@patch.object(Node, 'set_maintenance_off', set_maintenance_mock)
def test_set_maintenance_off(skale_bp, skale):
    data = post_bp_data(skale_bp, '/api/node/maintenance-off')
    assert data == {'payload': {}, 'status': 'ok'}


@patch.object(Node, 'set_domain_name', set_domain_name_mock)
def test_set_domain_name(skale_bp, skale):
    json_data = {'domain_name': 'skale.test'}
    data = post_bp_data(skale_bp, '/api/node/set-domain-name', json_data)
    assert data == {'payload': {}, 'status': 'ok'}
