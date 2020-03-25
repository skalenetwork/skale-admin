import pytest
import json
import os

from tests.utils import get_bp_data
from web.routes.schains import construct_schains_bp
from core.node_config import NodeConfig
from tools.docker_utils import DockerUtils
from flask import Flask

from web.models.schain import SChainRecord
from skale.contracts.data.schains_data import FIELDS
from core.schains.runner import get_image_name
from core.schains.config import get_schain_config_filepath
from tools.configs.containers import SCHAIN_CONTAINER

from skale.utils.contracts_provision.utils import generate_random_node_data


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    config.id = skale.nodes_data.get_active_node_ids()[0]
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_schains_bp(skale, config, dutils))
    SChainRecord.create_table()
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, wait_for=True)
    yield app.test_client()
    SChainRecord.drop_table()
    node_idx = skale.nodes_data.node_name_to_index(name)
    skale.manager.delete_node_by_root(node_idx, wait_for=True)


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
    cont1 = dutils.client.containers.run(schain_image, name='skale_schain_test_list', detach=True)
    data = get_bp_data(skale_bp, '/containers/schains/list', {'all': True})
    assert sum(map(lambda cont: cont['name'] == cont1.name, data)) == 1
    cont1.remove(force=True)


def test_owner_schains(skale_bp, skale):
    pass
