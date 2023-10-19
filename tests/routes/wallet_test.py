import pytest
from flask import Flask, appcontext_pushed, g
from skale.wallets.web3_wallet import to_checksum_address

from tests.utils import get_bp_data, init_web3_wallet, post_bp_data
from web.routes.wallet import wallet_bp
from web.helper import get_api_url


BLUEPRINT_NAME = 'wallet'


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(wallet_bp)

    def handler(sender, **kwargs):
        g.wallet = init_web3_wallet()

    with appcontext_pushed.connected_to(handler, app):
        yield app.test_client()


def test_load_wallet(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'info'))
    address = skale.wallet.address
    eth_balance_wei = skale.web3.eth.get_balance(address)
    expected_data = {
        'status': 'ok',
        'payload': {
            'address': to_checksum_address(address),
            'eth_balance_wei': eth_balance_wei,
            'skale_balance_wei': 0,  # TODO: Remove from node cli
            'eth_balance': str(skale.web3.from_wei(eth_balance_wei, 'ether')),
            'skale_balance': '0'  # TODO: Remove from node cli
        }
    }
    assert data == expected_data


def test_send_eth(skale_bp, skale):
    address = skale.wallet.address
    amount = '0.01'
    amount_wei = skale.web3.to_wei(amount, 'ether')
    receiver_0 = '0xf38b5dddd74b8901c9b5fb3ebd60bf5e7c1e9763'
    checksum_receiver_0 = to_checksum_address(receiver_0)
    receiver_balance_0 = skale.web3.eth.get_balance(checksum_receiver_0)
    balance_0 = skale.web3.eth.get_balance(address)
    json_data = {
        'address': receiver_0,
        'amount': amount
    }
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'send-eth'), json_data)
    balance_1 = skale.web3.eth.get_balance(address)
    assert data == {'status': 'ok', 'payload': {}}
    assert balance_1 < balance_0
    assert skale.web3.eth.get_balance(checksum_receiver_0) - \
        receiver_balance_0 == amount_wei

    receiver_1 = '0x01C19c5d3Ad1C3014145fC82263Fbae09e23924A'
    receiver_balance_1 = skale.web3.eth.get_balance(receiver_1)
    json_data = {
        'address': receiver_1,
        'amount': amount
    }
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'send-eth'), json_data)
    assert data == {'status': 'ok', 'payload': {}}
    assert skale.web3.eth.get_balance(address) < balance_1
    assert skale.web3.eth.get_balance(receiver_1) - \
        receiver_balance_1 == amount_wei


def test_send_eth_with_error(skale_bp, skale):
    json_data = {
        'address': '0x0000000',
        'amount': '0.1'
    }
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'send-eth'), json_data)
    assert data == {'status': 'error', 'payload': 'Funds sending failed'}
