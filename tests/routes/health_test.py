import mock
import pytest

from flask import Flask
from sgx import SgxClient

from core.node_config import NodeConfig

from tools.docker_utils import DockerUtils
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER

from web.routes.health import construct_health_bp
from web.helper import get_api_url

from tests.utils import get_bp_data


TEST_SGX_KEYNAME = 'test_keyname'


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    config = NodeConfig()
    config.id = 1
    app.register_blueprint(construct_health_bp(config, skale, dutils))
    return app.test_client()


def test_containers(skale_bp):
    data = get_bp_data(skale_bp, get_api_url('health', 'containers'))
    dutils = DockerUtils(volume_driver='local')
    expected = {
        'status': 'ok',
        'payload': dutils.get_containers_info(
            _all=False,
            name_filter='',
            format=True
        )
    }
    assert data == expected


def test_schains_checks(skale_bp, skale):
    class SChainChecksMock:
        def __init__(self, name, node_id, log=False, failhook=None):
            pass

        def get_all(self):
            return {
                'data_dir': False,
                'dkg': False,
                'config': True,
                'volume': False,
                'container': True,
                'ima_container': False,
                'firewall_rules': True,
                'rpc': False
            }

    def get_schains_for_node_mock(node_id):
        return [{'name': 'test-schain'}, {'name': ''}]

    with mock.patch('web.routes.schains.SChainChecks', SChainChecksMock):
        with mock.patch.object(skale.schains, 'get_schains_for_node',
                               get_schains_for_node_mock):
            data = get_bp_data(skale_bp, get_api_url('health', 'schains-checks'))
            assert data['status'] == 'ok'
            payload = data['payload']
            assert len(payload) == 1
            test_schain_checks = payload[0]['healthchecks']
            assert test_schain_checks == {
                'data_dir': False,
                'dkg': False,
                'config': True,
                'volume': False,
                'container': True,
                'ima_container': False,
                'firewall_rules': True,
                'rpc': False
            }


def test_sgx(skale_bp, skale):
    config = NodeConfig()
    config.sgx_key_name = TEST_SGX_KEYNAME

    data = get_bp_data(skale_bp, get_api_url('health', 'sgx'))
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
