import json
import mock
import os
import shutil

import docker
import pytest
from flask import Flask, appcontext_pushed, g

from core.node_config import NodeConfig
from core.schains.runner import get_image_name
from core.schains.config.helper import get_schain_config_filepath
from tests.utils import get_bp_data, post_bp_data
from tools.docker_utils import DockerUtils
from tools.configs.containers import SCHAIN_CONTAINER
from tools.iptables import NodeEndpoint
from web.models.schain import SChainRecord
from web.routes.schains import construct_schains_bp

from Crypto.Hash import keccak


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(construct_schains_bp())

    def handler(sender, **kwargs):
        g.docker_utils = DockerUtils(volume_driver='local')
        g.wallet = skale.wallet
        g.config = NodeConfig()
        g.config.id = 1

    with appcontext_pushed.connected_to(handler, app):
        SChainRecord.create_table()
        yield app.test_client()
        SChainRecord.drop_table()


def test_dkg_status(skale_bp):
    SChainRecord.add("test1")
    SChainRecord.add("test2")
    SChainRecord.add("test3")

    data = get_bp_data(skale_bp, '/api/dkg/statuses')
    assert data['status'] == 'ok'
    assert len(data['payload']) == 3, data

    SChainRecord.get_by_name("test3").set_deleted()
    data = get_bp_data(skale_bp, '/api/dkg/statuses')
    assert data['status'] == 'ok'
    assert len(data['payload']) == 2

    data = get_bp_data(skale_bp, '/api/dkg/statuses', {'all': True})
    assert data['status'] == 'ok'
    payload = data['payload']
    assert len(payload) == 3
    assert payload[2]['is_deleted'] is True


def test_node_schains_list(skale_bp, skale):
    data = get_bp_data(skale_bp, '/schains/list')
    assert data == {'payload': [], 'status': 'ok'}


def test_schain_config(skale_bp, skale, schain_config, schain_on_contracts):
    name = schain_on_contracts
    filename = get_schain_config_filepath(name)
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        os.makedirs(os.path.dirname(filename))
    with open(filename, 'w') as f:
        text = {'skaleConfig': {'nodeInfo': {'nodeID': 1}}}
        f.write(json.dumps(text))
    data = get_bp_data(skale_bp, '/schain-config', {'schain-name': name})
    assert data == {'payload': {'nodeInfo': {'nodeID': 1}},
                    'status': 'ok'}
    os.remove(filename)
    shutil.rmtree(os.path.dirname(filename))


def test_schains_containers_list(skale_bp, skale):
    dutils = DockerUtils(volume_driver='local')
    client = docker.client.from_env()
    try:
        phantom_container = client.containers.get(
            'skale_schain_test_list'
        )
    except docker.errors.NotFound:
        pass
    else:
        phantom_container.remove(force=True)

    schain_image = get_image_name(SCHAIN_CONTAINER)
    cont1 = dutils.client.containers.run(
        schain_image, name='skale_schain_test_list', detach=True)
    data = get_bp_data(skale_bp, '/containers/schains/list', {'all': True})
    assert data['status'] == 'ok'
    payload = data['payload']
    assert sum(map(lambda cont: cont['name'] == cont1.name, payload)) == 1
    cont1.remove(force=True)


def test_owner_schains(skale_bp, skale, schain_on_contracts):
    data = get_bp_data(skale_bp, '/get-owner-schains')
    assert data['status'] == 'ok'
    payload = data['payload']
    assert len(payload)
    schain_data = payload[0].copy()
    assert schain_data == skale.schains.get_schains_for_owner(
        skale.wallet.address)[0]


def get_allowed_endpoints_mock(schain):
    return [
        NodeEndpoint(ip='11.11.11.11', port='1111'),
        NodeEndpoint(ip='12.12.12.12', port=None),
        NodeEndpoint(ip=None, port='1313')
    ]


def schain_config_exists_mock(schain):
    return True


@mock.patch('web.routes.schains.get_allowed_endpoints',
            get_allowed_endpoints_mock)
@mock.patch('web.routes.schains.schain_config_exists',
            schain_config_exists_mock)
def test_get_firewall_rules(skale_bp):
    data = get_bp_data(skale_bp, '/api/schains/firewall/show',
                       params={'schain': 'schain-test'})
    assert data == {
        'payload': {
            'endpoints': [
                {'ip': '11.11.11.11', 'port': '1111'},
                {'ip': '12.12.12.12', 'port': None},
                {'ip': None, 'port': '1313'}
            ]},
        'status': 'ok'
    }


def test_schains_healthchecks(skale_bp, skale):
    class SChainChecksMock:
        def __init__(self, name, node_id, rotation_id=0):
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

    def get_schains_for_node_mock(skale, node_id):
        return [{'name': 'test-schain'}]

    def get_rotation_mock(schain_name):
        return {'rotation_id': 1}

    with mock.patch('web.routes.schains.SChainChecks', SChainChecksMock), \
        mock.patch('web.routes.schains.get_cleaned_schains_for_node',
                   get_schains_for_node_mock):
        data = get_bp_data(skale_bp, '/api/schains/healthchecks')
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


def test_enable_repair_mode(skale_bp, schain_db):
    schain_name = schain_db
    data = post_bp_data(skale_bp, '/api/schains/repair',
                        params={'schain': schain_name})
    assert data == {
        'payload': {},
        'status': 'ok'
    }

    data = post_bp_data(skale_bp, '/api/schains/repair',
                        params={'schain': 'undefined-schain'})
    assert data == {
        'payload': 'No schain with name undefined-schain',
        'status': 'error'
    }


def test_get_schain(skale_bp, skale, schain_db, schain_on_contracts):
    schain_name = schain_on_contracts
    keccak_hash = keccak.new(data=schain_name.encode("utf8"), digest_bits=256)
    schain_id = '0x' + keccak_hash.hexdigest()

    data = get_bp_data(skale_bp, '/api/schains/get',
                       params={'schain': schain_name})
    assert data == {
        'status': 'ok',
        'payload': {
            'name': schain_name,
            'id': schain_id,
            'owner': skale.wallet.address,
            'part_of_node': 0, 'dkg_status': 1, 'is_deleted': False,
            'first_run': True, 'repair_mode': False
        }
    }

    data = get_bp_data(skale_bp, '/api/schains/get',
                       params={'schain': 'undefined-schain'})
    assert data == {
        'payload': 'No schain with name undefined-schain',
        'status': 'error'
    }


def test_skaled_version(skale_bp):
    version = '3.4.1-beta.0'
    with mock.patch(
        'web.routes.schains.get_skaled_version',
        return_value=version

    ):
        data = get_bp_data(skale_bp, '/skaled-version')
        assert data == {'status': 'ok', 'payload': {'version': version}}
