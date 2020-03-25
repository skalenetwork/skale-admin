import pytest
import os
import tarfile
from flask import Flask

from tools.configs import NODE_DATA_PATH
from tests.utils import get_bp_data
from web.routes.logs import web_logs


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(web_logs)
    return app.test_client()


def test_get_logs(skale_bp):
    name = 'test1'
    data = get_bp_data(skale_bp, '/logs/dump', {'container_name': name}, full_data=True)
    schain_log_path = os.path.join(NODE_DATA_PATH, 'logs.tar.gz')
    with open(schain_log_path, 'wb') as f:
        f.write(data)
    tar = tarfile.open(schain_log_path, "r:gz")
    assert f'skale_schain_{name}.log' in tar.getnames()
    os.remove(schain_log_path)
