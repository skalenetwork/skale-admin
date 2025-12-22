from unittest import mock

import pytest
from flask import Flask, appcontext_pushed, g

from core.checks.schain import SChainChecks
from core.node_config import NodeConfig
from tests.utils import get_bp_data, get_schain_struct
from web.helper import get_api_url
from web.models.schain import SChainRecord
from web.routes.health import health_bp

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


def test_schains_checks(skale_bp, skale, schain_on_contracts, schain_db, dutils):
    schain_name = schain_db

    class SChainChecksMock(SChainChecks):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, dutils=dutils, **kwargs)

    def schains_for_node_mock(self, node_id):
        return [
            get_schain_struct(_test_schain_name=schain_name),
            get_schain_struct(_test_schain_name='test-schain'),
            get_schain_struct(_test_schain_name=''),
        ]

    with mock.patch('web.routes.health.SChainChecks', SChainChecksMock):
        with mock.patch(
            'skale.contracts.manager.schains.SChains.schains_for_node',
            schains_for_node_mock,
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
                'firewall_rules': False,
                'skaled_container': False,
                'exit_code_ok': True,
                'rpc': False,
                'blocks': False,
                'process': False,
                'ima_container': False,
            }

            request_params = {'checks_filter': 'skaled_container,volume,config'}
            data = get_bp_data(skale_bp, get_api_url('health', 'schains'), params=request_params)

            assert data['payload'][0]['healthchecks'] == {
                'skaled_container': False,
                'volume': False,
                'config': False,
            }


def test_schains_checks_no_node(unregistered_skale_bp, skale):
    data = get_bp_data(unregistered_skale_bp, get_api_url('health', 'schains'))
    assert data['status'] == 'error'
    assert data['payload'] == 'No node installed'
