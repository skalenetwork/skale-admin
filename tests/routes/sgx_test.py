import pytest
from flask import Flask, appcontext_pushed, g

from sgx import SgxClient

from core.node_config import NodeConfig
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from web.routes.sgx import construct_sgx_bp

from tests.utils import get_bp_data

TEST_SGX_KEYNAME = 'test_keyname'


@pytest.fixture
def skale_bp():
    app = Flask(__name__)
    app.register_blueprint(construct_sgx_bp())

    def handler(sender, **kwargs):
        g.config = NodeConfig()

    with appcontext_pushed.connected_to(handler, app):
        yield app.test_client()
    return app.test_client()


def test_sgx_status(skale_bp):
    data = get_bp_data(skale_bp, '/api/sgx/info')
    sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
    version = sgx.get_server_version()
    assert data == {
        'status': 'ok',
        'payload': {
            'status': 0,
            'status_name': 'CONNECTED',
            'sgx_server_url': 'https://localhost:1026',
            'sgx_keyname': None, 'sgx_wallet_version': version
        }
    }
