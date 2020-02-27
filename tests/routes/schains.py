import pytest
import json

from web.routes.schains import construct_schains_bp
from core.node_config import NodeConfig
from tools.docker_utils import DockerUtils
from flask import Flask

from web.models.schain import SChainRecord


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_schains_bp(skale, config, dutils))
    return app.test_client()


def test_dks_status(skale_bp):
    SChainRecord.create_table()
    SChainRecord.add("test1")
    SChainRecord.add("test2")
    SChainRecord.add("test3")
    data = skale_bp.get('/api/dkg/statuses').data
    data = json.loads(data.decode('utf-8'))['data']
    assert len(data) == 3
