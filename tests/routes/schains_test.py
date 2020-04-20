import os

import pytest
import json
import mock
from flask import Flask
from skale.contracts.data.schains_data import FIELDS

from core.node_config import NodeConfig
from core.schains.config import get_schain_config_filepath
from core.schains.runner import get_image_name
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
    config.id = skale.nodes_data.get_active_node_ids()[0]
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
    assert len(data) == 3
    SChainRecord.get_by_name("test3").set_deleted()
    data = get_bp_data(skale_bp, '/api/dkg/statuses')
    assert len(data) == 2
    data = get_bp_data(skale_bp, '/api/dkg/statuses', {'all': True})
    assert len(data) == 3
    assert data[2]['is_deleted'] is True


def test_node_schains_list(skale_bp, skale):
    data = get_bp_data(skale_bp, '/schains/list')
    assert len(data) == 1
    assert len(data[0]) == len(FIELDS) + 1


def test_schain_config(skale_bp, skale):
    sid = skale.schains_data.get_all_schains_ids()[-1]
    name = skale.schains_data.get(sid).get('name')
    filename = get_schain_config_filepath(name)
    os.makedirs(os.path.dirname(filename))
    with open(filename, 'w') as f:
        text = {'skaleConfig': True}
        f.write(json.dumps(text))
    data = get_bp_data(skale_bp, '/schain-config', {'schain-name': name})
    assert data is True
    os.remove(filename)
    os.rmdir(os.path.dirname(filename))


def test_schains_containers_list(skale_bp, skale):
    dutils = DockerUtils(volume_driver='local')
    schain_image = get_image_name(SCHAIN_CONTAINER)
    cont1 = dutils.client.containers.run(
        schain_image, name='skale_schain_test_list', detach=True)
    data = get_bp_data(skale_bp, '/containers/schains/list', {'all': True})
    assert sum(map(lambda cont: cont['name'] == cont1.name, data)) == 1
    cont1.remove(force=True)


def test_owner_schains(skale_bp, skale):
    data = get_bp_data(skale_bp, '/get-owner-schains')
    assert len(data)
    assert len(data[0]['nodes'])
    schain_data = data[0].copy()
    schain_data.pop('nodes')
    assert schain_data == skale.schains_data.get_schains_for_owner(
        skale.wallet.address)[0]


def get_allowed_endpoints_mock(schain):
    return [
        NodeEndpoint(ip='11.11.11.11', port='1111'),
        NodeEndpoint(ip='12.12.12.12', port=None),
        NodeEndpoint(ip=None, port='1313')
    ]


def test_firewall_rules_show(skale_bp):
    with mock.patch('web.routes.schains.get_allowed_endpoints',
                    get_allowed_endpoints_mock):
        data = get_bp_data(skale_bp, '/api/schains/firewall/show')
        assert data == {
            'payload': {
                'endpoints': [
                    {'ip': '11.11.11.11', 'port': '1111'},
                    {'ip': '12.12.12.12', 'port': None},
                    {'ip': None, 'port': '1313'}
                ]},
            'status': 'ok'
        }


def test_firewall_rules_on(skale_bp):
    with mock.patch('web.routes.schains.get_allowed_endpoints',
                    get_allowed_endpoints_mock):
        with mock.patch('web.routes.schains.add_iptables_rules'):
            data = post_bp_data(skale_bp, '/api/schains/firewall/on')
            assert data == {'status': 'ok'}


def test_firewall_rules_off(skale_bp):
    with mock.patch('web.routes.schains.get_allowed_endpoints',
                    get_allowed_endpoints_mock):
        with mock.patch('web.routes.schains.remove_iptables_rules'):
            data = post_bp_data(skale_bp, '/api/schains/firewall/off')
            assert data == {'status': 'ok'}
