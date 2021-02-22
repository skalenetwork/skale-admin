import datetime

import pytest
import mock
from mock import patch
import freezegun

from flask import Flask, appcontext_pushed, g
from web3 import Web3

from core.node import Node
from core.node_config import NodeConfig

from web.routes.nodes import construct_nodes_bp
from web.helper import get_api_url

from tools.docker_utils import DockerUtils
from tools.configs.tg import TG_API_KEY, TG_CHAT_ID

from tests.utils import get_bp_data, post_bp_data

from skale.utils.contracts_provision.utils import generate_random_node_data
from skale.utils.contracts_provision import DEFAULT_DOMAIN_NAME


CURRENT_TIMESTAMP = 1594903080
CURRENT_DATETIME = datetime.datetime.utcfromtimestamp(CURRENT_TIMESTAMP)

BLUEPRINT_NAME = 'node'


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


def test_node_info(skale_bp, node):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'info'))
    assert data == {'status': 'ok', 'payload': {'node_info': node.info}}


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
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'register'), json_data)
    assert data == {'status': 'ok', 'payload': {'node_data': 1}}

    # Without gas_limit
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_price': 2 * 10 ** 9
    }
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'register'), json_data)
    assert data == {'status': 'ok', 'payload': {'node_data': 1}}

    # Without gas_limit and gas_price
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port,
        'gas_price': 2 * 10 ** 9
    }
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'register'), json_data)
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
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'register'), json_data)
    assert data == {'payload': ['Already registered'], 'status': 'error'}


def get_expected_signature(skale, validator_id):
    unsigned_hash = Web3.soliditySha3(['uint256'], [validator_id])
    signed_hash = skale.wallet.sign_hash(unsigned_hash.hex())
    return signed_hash.signature.hex()


def test_node_signature(skale_bp, skale):
    validator_id = 1
    json_data = {'validator_id': validator_id}
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'signature'), json_data)
    expected_signature = get_expected_signature(skale, validator_id)
    assert data == {'status': 'ok', 'payload': {
        'signature': expected_signature}}


@patch.object(Node, 'set_maintenance_on', set_maintenance_mock)
def test_set_maintenance_on(skale_bp, skale):
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'maintenance-on'))
    assert data == {'payload': {}, 'status': 'ok'}


@patch.object(Node, 'set_maintenance_off', set_maintenance_mock)
def test_set_maintenance_off(skale_bp, skale):
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'maintenance-off'))
    assert data == {'payload': {}, 'status': 'ok'}


@patch.object(Node, 'set_domain_name', set_domain_name_mock)
def test_set_domain_name(skale_bp, skale):
    json_data = {'domain_name': 'skale.test'}
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'set-domain-name'), json_data)
    assert data == {'payload': {}, 'status': 'ok'}


@freezegun.freeze_time(CURRENT_DATETIME)
def test_send_tg_notification(skale_bp):
    with mock.patch(
        'tools.notifications.messages.send_message_to_telegram',
        mock.Mock(return_value={'message': 'test'})
    ) as send_message_to_telegram_mock:
        data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'send-tg-notification'),
                            {'message': ['test']})
        send_message_to_telegram_mock.delay.assert_called_once_with(
            TG_API_KEY,
            TG_CHAT_ID,
            'test\n\nTimestamp: 1594903080\n'
            'Datetime: Thu Jul 16 12:38:00 2020'
        )

    expected = {'status': 'ok',
                'payload': 'Message was sent successfully'}
    assert data == expected


def test_endpoint_info(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'endpoint-info'))
    assert data['status'] == 'ok'
    payload = data['payload']
    assert payload['syncing'] is False
    assert payload['block_number'] > 1
    assert payload['trusted'] is False


def test_meta_info(skale_bp):
    meta_info = {"version": "0.0.0", "config_stream": "1.4.1-testnet"}

    with mock.patch(
        'web.routes.node_info.get_meta_info',
        return_value=meta_info
    ):
        data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'meta-info'))
        assert data == {'status': 'ok', 'payload': meta_info}