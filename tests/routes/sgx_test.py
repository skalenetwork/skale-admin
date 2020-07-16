import pytest
from flask import Flask

from sgx import SgxClient

from core.node_config import NodeConfig
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from web.routes.sgx import sgx_bp

from tests.utils import get_bp_data


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(sgx_bp)
    return app.test_client()


def test_sgx_status(skale_bp, skale):
    data = get_bp_data(skale_bp, '/api/sgx/info')
    TEST_SGX_KEYNAME= 'test_keyname'

    sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
    version = sgx.get_server_version()

    config = NodeConfig()
    config.sgx_key_name = TEST_SGX_KEYNAME
    
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
