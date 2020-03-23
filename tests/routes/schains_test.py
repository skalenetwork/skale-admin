import pytest
import json

from web.routes.schains import construct_schains_bp
from core.node_config import NodeConfig
from tools.docker_utils import DockerUtils
from flask import Flask

from web.models.schain import SChainRecord
from skale.contracts.data.schains_data import FIELDS


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


def get_bp_data(bp, request, params=None):
    data = bp.get(request, query_string=params).data
    return json.loads(data.decode('utf-8'))['data']


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


def test_owner_schains(skale_bp, skale):
    data = get_bp_data(skale_bp, '/schains/list')
    assert len(data) == 1
    assert len(data[0]) == len(FIELDS) + 1
