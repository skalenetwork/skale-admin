import json
import mock
import os
import shutil
from functools import partial

import pytest
from flask import Flask, appcontext_pushed, g
from Crypto.Hash import keccak

from core.node_config import NodeConfig
from core.schains.config.file_manager import ConfigFileManager
from tests.utils import get_bp_data, get_test_rule_controller
from web.models.schain import SChainRecord, upsert_schain_record
from web.routes.schains import schains_bp
from web.helper import get_api_url


BLUEPRINT_NAME = 'schains'


@pytest.fixture
def skale_bp(skale, dutils):
    app = Flask(__name__)
    app.register_blueprint(schains_bp)

    def handler(sender, **kwargs):
        g.docker_utils = dutils
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = 1

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        yield app.test_client()
        SChainRecord.drop_table()


def test_schain_statuses(skale_bp, skaled_status, _schain_name):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'statuses'))
    assert data['status'] == 'ok'
    assert data['payload'][_schain_name] == skaled_status.all


def test_schain_config(skale_bp, skale, schain_config, schain_on_contracts):
    name = schain_on_contracts
    filepath = ConfigFileManager(name).skaled_config_path
    dirname = os.path.dirname(filepath)
    if not os.path.isdir(dirname):
        os.makedirs(os.path.dirname(filepath))
    try:
        with open(filepath, 'w') as f:
            text = {'skaleConfig': {'nodeInfo': {'nodeID': 1}}}
            f.write(json.dumps(text))
        data = get_bp_data(skale_bp, get_api_url(
            BLUEPRINT_NAME, 'config'), {'schain_name': name})
        assert data == {'payload': {'nodeInfo': {'nodeID': 1}},
                        'status': 'ok'}
    finally:
        os.remove(filepath)
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)


def test_schains_list(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'list'))
    assert data == {'payload': [], 'status': 'ok'}


def schain_config_exists_mock(schain):
    return True


@mock.patch(
    'web.routes.schains.get_default_rule_controller',
    partial(get_test_rule_controller, synced=True)
)
def test_firewall_rules_route(skale_bp, schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'firewall-rules'),
                       params={'schain_name': schain_name})
    assert data == {
        'status': 'ok',
        'payload': {
            'endpoints': [
                {'port': 10000, 'first_ip': '127.0.0.2', 'last_ip': '127.0.0.2'},
                {'port': 10001, 'first_ip': '127.0.0.2', 'last_ip': '127.0.0.2'},
                {'port': 10002, 'first_ip': None, 'last_ip': None},
                {'port': 10003, 'first_ip': None, 'last_ip': None},
                {'port': 10004, 'first_ip': '127.0.0.2', 'last_ip': '127.0.0.2'},
                {'port': 10005, 'first_ip': '127.0.0.2', 'last_ip': '127.0.0.2'},
                {'port': 10007, 'first_ip': None, 'last_ip': None},
                {'port': 10008, 'first_ip': None, 'last_ip': None},
                {'port': 10009, 'first_ip': None, 'last_ip': None},
                {'port': 10010, 'first_ip': '127.0.0.2', 'last_ip': '127.0.0.2'}
            ]
        }
    }


def test_get_schain(
    skale_bp,
    skale,
    schain_db,
    meta_file,
    schain_on_contracts
):
    schain_name = schain_on_contracts
    keccak_hash = keccak.new(data=schain_name.encode("utf8"), digest_bits=256)
    schain_id = '0x' + keccak_hash.hexdigest()

    r = upsert_schain_record(schain_name)
    r.set_config_version(meta_file['config_stream'])
    data = get_bp_data(
        skale_bp,
        get_api_url(BLUEPRINT_NAME, 'get'),
        params={'schain_name': schain_name}
    )
    assert data == {
        'status': 'ok',
        'payload': {
            'name': schain_name,
            'id': schain_id,
            'mainnet_owner': skale.wallet.address,
            'part_of_node': 1, 'dkg_status': 1, 'is_deleted': False,
            'first_run': True, 'repair_mode': False
        }
    }

    not_existing_schain = 'not-existing-schain'
    data = get_bp_data(
        skale_bp,
        get_api_url(BLUEPRINT_NAME, 'get'),
        params={'schain_name': not_existing_schain}
    )
    assert data == {
        'payload': f'No schain with name {not_existing_schain}',
        'status': 'error'
    }


def test_schain_containers_versions(skale_bp):
    expected_skaled_version = '3.19.0'
    expected_ima_version = '2.1.0'
    data = get_bp_data(skale_bp, get_api_url(
        BLUEPRINT_NAME, 'container-versions'))
    assert data == {
        'status': 'ok',
        'payload': {
            'skaled_version': expected_skaled_version,
            'ima_version': expected_ima_version
        }
    }
