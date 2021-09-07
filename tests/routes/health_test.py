import mock
import pytest

from flask import Flask, appcontext_pushed, g
from sgx import SgxClient

from core.node_config import NodeConfig

from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER

from web.models.schain import SChainRecord
from web.routes.health import construct_health_bp
from web.helper import get_api_url

from tests.utils import get_bp_data


TEST_SGX_KEYNAME = 'test_keyname'


@pytest.fixture
def skale_bp(skale, dutils):
    app = Flask(__name__)
    app.register_blueprint(construct_health_bp())

    def handler(sender, **kwargs):
        g.docker_utils = dutils
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = 1

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        yield app.test_client()
        SChainRecord.drop_table()


@pytest.fixture
def unregistered_skale_bp(skale, dutils):
    app = Flask(__name__)
    app.register_blueprint(construct_health_bp())

    def handler(sender, **kwargs):
        g.docker_utils = dutils
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = None

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        yield app.test_client()
        SChainRecord.drop_table()


def test_containers(skale_bp, dutils):
    data = get_bp_data(skale_bp, get_api_url('health', 'containers'))
    expected = {
        'status': 'ok',
        'payload': dutils.get_containers_info(
            all=False,
            name_filter='',
            format=True
        )
    }
    assert data == expected


def test_schains_checks(skale_bp, skale, schain_db):
    schain_name = schain_db

    class SChainChecksMock:
        def __init__(
            self,
            name,
            node_id,
            *args,
            log=False,
            failhook=None,
            **kwargs
        ):
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

    def get_schains_for_node_mock(self, node_id):
        return [
            {'name': schain_name},
            {'name': 'test-schain'},
            {'name': ''}
        ]

    with mock.patch('web.routes.health.SChainChecks', SChainChecksMock):
        with mock.patch(
            'skale.contracts.manager.schains.SChains.get_schains_for_node',
            get_schains_for_node_mock
        ):
            data = get_bp_data(skale_bp, get_api_url('health', 'schains'))
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


def test_schains_checks_no_node(unregistered_skale_bp, skale):
    data = get_bp_data(unregistered_skale_bp, get_api_url('health', 'schains'))
    assert data['status'] == 'error'
    assert data['payload'] == 'No node installed'


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
