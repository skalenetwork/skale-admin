import pytest
from flask import Flask

from core.node_config import NodeConfig
from tests.utils import get_bp_data
from web.routes.metrics import construct_metrics_bp


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    config = NodeConfig()
    app.register_blueprint(construct_metrics_bp(skale, config))
    return app.test_client()


def test_metrics(skale_bp):
    data = get_bp_data(skale_bp, '/metrics')
    assert data
    assert list(data.keys()) == ['metrics', 'total']
