import pytest

from web.routes.validators import construct_validators_bp
from core.node_config import NodeConfig
from flask import Flask


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    config.id = skale.nodes_data.get_active_node_ids()[0]
    app.register_blueprint(construct_validators_bp(skale, config))
    return app.test_client()
