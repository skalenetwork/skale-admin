import json
import mock
import os
import shutil

import pytest
from flask import Flask, appcontext_pushed, g

from core.node_config import NodeConfig
from core.schains.config.directory import schain_config_filepath
from tests.utils import get_bp_data, get_test_rc_synced, post_bp_data
from web.models.schain import SChainRecord
from web.routes.schains import construct_schains_bp
from web.helper import get_api_url

from Crypto.Hash import keccak


BLUEPRINT_NAME = 'schains'


@pytest.fixture
def skale_bp(skale, dutils):
    app = Flask(__name__)
    app.register_blueprint(construct_schains_bp())

    def handler(sender, **kwargs):
        g.docker_utils = dutils
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = 1

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        yield app.test_client()
        SChainRecord.drop_table()


def test_schain_config(skale_bp, skale, schain_config, schain_on_contracts):
    name = schain_on_contracts
    filename = schain_config_filepath(name)
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        os.makedirs(os.path.dirname(filename))
    with open(filename, 'w') as f:
        text = {'skaleConfig': {'nodeInfo': {'nodeID': 1}}}
        f.write(json.dumps(text))
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'config'), {'schain_name': name})
    assert data == {'payload': {'nodeInfo': {'nodeID': 1}},
                    'status': 'ok'}
    os.remove(filename)
    shutil.rmtree(os.path.dirname(filename))


def test_schains_list(skale_bp, skale):
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'list'))
    assert data == {'payload': [], 'status': 'ok'}


def schain_config_exists_mock(schain):
    return True


@mock.patch('web.routes.schains.schain_config_exists', schain_config_exists_mock)
@mock.patch('web.routes.schains.get_default_rule_controller', get_test_rc_synced)
def test_firewall_rules_route(skale_bp, schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'firewall-rules'),
                       params={'schain_name': schain_name})
    print(data)
    assert data == {
        'status': 'ok',
        'payload': {
            'endpoints': [
                {'port': 10000, 'first_ip': '127.0.0.2', 'last_ip': None},
                {'port': 10001, 'first_ip': '127.0.0.2', 'last_ip': None},
                {'port': 10002, 'first_ip': None, 'last_ip': None},
                {'port': 10003, 'first_ip': None, 'last_ip': None},
                {'port': 10004, 'first_ip': '127.0.0.2', 'last_ip': None},
                {'port': 10005, 'first_ip': '127.0.0.2', 'last_ip': None},
                {'port': 10007, 'first_ip': None, 'last_ip': None},
                {'port': 10008, 'first_ip': None, 'last_ip': None},
                {'port': 10009, 'first_ip': None, 'last_ip': None},
                {'port': 10010, 'first_ip': None, 'last_ip': None},
                {'port': 10011, 'first_ip': None, 'last_ip': None},
                {'port': 10012, 'first_ip': None, 'last_ip': None},
                {'port': 10013, 'first_ip': None, 'last_ip': None}
            ]
        }
    }


def test_enable_repair_mode(skale_bp, schain_db):
    schain_name = schain_db
    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'repair'),
                        params={'schain_name': schain_name})
    assert data == {
        'payload': {},
        'status': 'ok'
    }

    data = post_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'repair'),
                        params={'schain_name': 'undefined-schain'})
    assert data == {
        'payload': 'No schain with name undefined-schain',
        'status': 'error'
    }


def test_get_schain(skale_bp, skale, schain_db, schain_on_contracts):
    schain_name = schain_on_contracts
    keccak_hash = keccak.new(data=schain_name.encode("utf8"), digest_bits=256)
    schain_id = '0x' + keccak_hash.hexdigest()

    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'get'),
                       params={'schain_name': schain_name})
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

    data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'get'),
                       params={'schain_name': 'undefined-schain'})
    assert data == {
        'payload': 'No schain with name undefined-schain',
        'status': 'error'
    }


def test_schain_containers_versions(skale_bp):
    skaled_version = '3.7.3-develop.4'
    ima_version = '1.1.0-beta.0'
    with mock.patch(
        'web.routes.schains.get_skaled_version',
        return_value=skaled_version
    ), mock.patch('web.routes.schains.get_ima_version',
                  return_value=ima_version):
        data = get_bp_data(skale_bp, get_api_url(BLUEPRINT_NAME, 'container-versions'))
        assert data == {
            'status': 'ok',
            'payload': {
                'skaled_version': skaled_version,
                'ima_version': ima_version
            }
        }
