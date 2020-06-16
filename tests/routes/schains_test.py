import os

import pytest
import json
import mock
from flask import Flask

from core.node_config import NodeConfig

import docker

from core.schains.runner import get_image_name
from core.schains.config import get_schain_config_filepath
from tests.utils import get_bp_data, post_bp_data
from tools.docker_utils import DockerUtils
from tools.configs.containers import SCHAIN_CONTAINER
from tools.iptables import NodeEndpoint
from web.models.schain import SChainRecord
from web.routes.schains import construct_schains_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    config.id = 1  # skale.nodes.get_active_node_ids()[0]
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_schains_bp(skale, config, dutils))
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


def test_schain_config(skale_bp, skale):
    sid = skale.schains_internal.get_all_schains_ids()[-1]
    name = skale.schains.get(sid).get('name')
    filename = get_schain_config_filepath(name)
    os.makedirs(os.path.dirname(filename))
    with open(filename, 'w') as f:
        text = {'skaleConfig': True}
        f.write(json.dumps(text))
    data = get_bp_data(skale_bp, '/schain-config', {'schain-name': name})
    assert data == {'payload': True, 'status': 'ok'}
    os.remove(filename)
    os.rmdir(os.path.dirname(filename))


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


def test_owner_schains(skale_bp, skale):
    data = get_bp_data(skale_bp, '/get-owner-schains')
    assert data['status'] == 'ok'
    payload = data['payload']
    assert len(payload)
    assert len(payload[0]['nodes'])
    schain_data = payload[0].copy()
    schain_data.pop('nodes')
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


@mock.patch('web.routes.schains.get_allowed_endpoints', get_allowed_endpoints_mock)
@mock.patch('web.routes.schains.schain_config_exists', schain_config_exists_mock)
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


@mock.patch('web.routes.schains.get_allowed_endpoints', get_allowed_endpoints_mock)
@mock.patch('web.routes.schains.schain_config_exists', schain_config_exists_mock)
@mock.patch('web.routes.schains.add_iptables_rules', new=mock.Mock())
def test_firewall_rules_on(skale_bp):
    data = post_bp_data(skale_bp, '/api/schains/firewall/on',
                        params={'schain': 'test-schain'})
    assert data == {'status': 'ok', 'payload': {}}


@mock.patch('web.routes.schains.get_allowed_endpoints', get_allowed_endpoints_mock)
@mock.patch('web.routes.schains.schain_config_exists', schain_config_exists_mock)
@mock.patch('web.routes.schains.remove_iptables_rules', new=mock.Mock())
def test_firewall_rules_off(skale_bp):
    data = post_bp_data(skale_bp, '/api/schains/firewall/off',
                        params={'schain': 'test-schain'})
    assert data == {'status': 'ok', 'payload': {}}


def test_schains_healthchecks(skale_bp, skale):
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
        return [{
            'name': 'test-schain'
        }]

    with mock.patch('web.routes.schains.SChainChecks', SChainChecksMock):
        with mock.patch.object(skale.schains, 'get_schains_for_node',
                               get_schains_for_node_mock):
            data = get_bp_data(skale_bp, '/api/schains/healthchecks')
            assert data['status'] == 'ok'
            payload = data['payload']
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
