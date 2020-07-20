import pytest
from flask import Flask

from sgx import SgxClient

from core.node_config import NodeConfig
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from web.routes.sgx import construct_sgx_bp

from tests.utils import get_bp_data

TEST_SGX_KEYNAME = 'test_keyname'


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    config.sgx_key_name = TEST_SGX_KEYNAME
    app.register_blueprint(construct_sgx_bp(config))
    return app.test_client()


def test_sgx_status(skale_bp, skale):
    data = get_bp_data(skale_bp, '/api/sgx/info')
    sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
    version = sgx.get_server_version()
    assert data == {
        'payload': {
            'sgx_server_url': SGX_SERVER_URL,
            'status': 0,
            'status_name': 'CONNECTED',
            'sgx_wallet_version': version,
            'sgx_keyname': TEST_SGX_KEYNAME,
        },
        'status': 'ok'
    }
