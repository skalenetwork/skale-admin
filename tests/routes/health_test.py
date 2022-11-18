import mock
import pytest
from time import sleep

from flask import Flask, appcontext_pushed, g
from sgx import SgxClient

from core.node_config import NodeConfig
from core.schains.checks import SChainChecks, CheckRes

from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER

from web.models.schain import SChainRecord
from web.routes.health import health_bp
from web.helper import get_api_url

from tests.utils import get_bp_data, run_custom_schain_container


TEST_SGX_KEYNAME = 'test_keyname'


@pytest.fixture
def skale_bp(skale, nodes, node_skales, dutils):
    app = Flask(__name__)
    app.register_blueprint(health_bp)

    def handler(sender, **kwargs):
        node_index = 0
        g.docker_utils = dutils
        g.wallet = node_skales[node_index].wallet
        g.config = NodeConfig()
        g.config.id = nodes[node_index]

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        try:
            yield app.test_client()
        finally:
            SChainRecord.drop_table()


@pytest.fixture
def unregistered_skale_bp(skale, dutils):
    app = Flask(__name__)
    app.register_blueprint(health_bp)

    def handler(sender, **kwargs):
        g.docker_utils = dutils
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = None

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        try:
            yield app.test_client()
        finally:
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


def test_containers_all(skale_bp, dutils, schain_db, cleanup_schain_containers):
    run_custom_schain_container(dutils, schain_db, 'bash -c "exit 1"')
    sleep(10)
    data = get_bp_data(skale_bp, get_api_url('health', 'containers'), params={'all': True})
    expected = {
        'status': 'ok',
        'payload': dutils.get_containers_info(
            all=True,
            name_filter='',
            format=True
        )
    }
    assert data == expected


def test_schains_checks(skale_bp, skale, schain_db, dutils):
    schain_name = schain_db

    class SChainChecksMock(SChainChecks):
        def __init__(self, *args, **kwargs):
            super(SChainChecksMock, self).__init__(*args, dutils=dutils, **kwargs)

        @property
        def firewall_rules(self) -> CheckRes:
            return CheckRes(True)

    def get_schains_for_node_mock(self, node_id):
        return [
            {'name': schain_name},
            {'name': 'test-schain'},
            {'name': ''}
        ]

    with mock.patch('web.routes.health.SChainChecks', SChainChecksMock), \
            mock.patch('web.routes.health.SChainChecks', SChainChecksMock):
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
                'config_dir': False,
                'dkg': False,
                'config': False,
                'volume': False,
                'firewall_rules': True,
                'skaled_container': False,
                'exit_code_ok': True,
                'rpc': False,
                'blocks': False,
                'process': False,
                'ima_container': False
            }

            request_params = {'checks_filter': 'skaled_container,volume,config'}
            data = get_bp_data(skale_bp, get_api_url('health', 'schains'), params=request_params)

            assert data['payload'][0]['healthchecks'] == {
                'skaled_container': False,
                'volume': False,
                'config': False
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
