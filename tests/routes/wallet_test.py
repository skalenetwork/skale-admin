import pytest
from flask import Flask
from skale.wallets.web3_wallet import to_checksum_address

from tests.utils import get_bp_data
from web.routes.wallet import construct_wallet_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_wallet_bp(skale))
    return app.test_client()


def test_load_wallet(skale_bp, skale):
    data = get_bp_data(skale_bp, '/load-wallet')
    address = skale.wallet.address
    eth_balance_wei = skale.web3.eth.getBalance(address)
    skale_balance_wei = skale.token.get_balance(address)
    expected_data = {
        'status': 'ok',
        'payload': {
            'address': to_checksum_address(address),
            'eth_balance_wei': eth_balance_wei,
            'skale_balance_wei': skale_balance_wei,
            'eth_balance': str(skale.web3.fromWei(eth_balance_wei, 'ether')),
            'skale_balance': str(skale.web3.fromWei(skale_balance_wei, 'ether'))
        }
    }
    assert data == expected_data
