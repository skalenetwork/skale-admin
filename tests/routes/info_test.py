from time import sleep

import pytest
from flask import Flask, appcontext_pushed, g
from sgx import SgxClient

from core.node_config import NodeConfig
from tests.utils import get_bp_data, run_custom_schain_container
from tools.configs import SGX_CERTIFICATES_FOLDER, SGX_SERVER_URL
from web.helper import get_api_url
from web.models.schain import SChainRecord
from web.routes.info import info_bp

TEST_SGX_KEYNAME = 'test_keyname'
BLUEPRINT_NAME = 'info'


@pytest.fixture
def skale_bp(skale, nodes, node_skales, dutils):
    app = Flask(__name__)
    app.register_blueprint(info_bp)

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
    app.register_blueprint(info_bp)

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


def test_sgx(skale_bp, skale):
    config = NodeConfig()
    config.sgx_key_name = TEST_SGX_KEYNAME

    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'sgx'))
    sgx = SgxClient(SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER)
    version = sgx.get_server_version()
    assert data == {
        'payload': {
            'sgx_server_url': SGX_SERVER_URL,
            'status_zmq': True,
            'status_https': True,
            'sgx_wallet_version': version,
            'sgx_keyname': TEST_SGX_KEYNAME,
        },
        'status': 'ok',
    }


def test_endpoint_info(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'endpoint-info'))
    assert data['status'] == 'ok'
    payload = data['payload']
    assert payload['syncing'] is False
    assert payload['block_number'] > 1
    assert payload['trusted'] is False
    assert payload['client'] != 'unknown'


def test_meta_info(skale_bp, meta_file):
    meta_info = meta_file
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'meta-info'))
    assert data == {'status': 'ok', 'payload': meta_info}


def test_btrfs_info(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'btrfs-info'))
    assert data['status'] == 'ok'
    payload = data['payload']
    assert payload['kernel_module'] is True


def test_containers(skale_bp, dutils):
    data = get_bp_data(skale_bp, get_api_url('info', 'containers'))
    expected = {
        'status': 'ok',
        'payload': dutils.get_containers_info(all=False, name_filter='', format=True),
    }
    assert data == expected
    for container_info in data['payload']:
        field_map = {'cpu_shares': 0, 'mem_limit': 0, 'swap_limit': 0, 'swappiness': None}
        for field in field_map.keys():
            assert field in container_info


def test_containers_all(skale_bp, dutils, schain_db, cleanup_schain_containers):
    run_custom_schain_container(dutils, schain_db, 'bash -c "exit 1"')
    sleep(10)
    data = get_bp_data(skale_bp, get_api_url('info', 'containers'), params={'all': True})
    expected = {
        'status': 'ok',
        'payload': dutils.get_containers_info(all=True, name_filter='', format=True),
    }
    assert data == expected
    for container_info in data['payload']:
        field_map = {'cpu_shares': 0, 'mem_limit': 0, 'swap_limit': 0, 'swappiness': None}
        for field in field_map.keys():
            assert field in container_info
