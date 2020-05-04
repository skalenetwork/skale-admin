import pytest
from flask import Flask

from tests.utils import get_bp_data
from tools.configs import SGX_SERVER_URL
from web.routes.sgx import sgx_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(sgx_bp)
    return app.test_client()


def test_sgx_status(skale_bp, skale):
    data = get_bp_data(skale_bp, '/api/sgx/status')
    assert data == {
        'payload': {
            'sgx_server_url': SGX_SERVER_URL,
            'status': 1,
            'status_name': 'NOT_CONNECTED'
        },
        'status': 'ok'
    }
