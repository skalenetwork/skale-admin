import pytest
from flask import Flask

from tests.utils import get_bp_data
from tools.wallet_utils import wallet_with_balance
from web.routes.wallet import construct_wallet_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_wallet_bp(skale))
    return app.test_client()


def test_sgx_status(skale_bp, skale):
    data = get_bp_data(skale_bp, '/load-wallet')
    assert data == wallet_with_balance(skale)
