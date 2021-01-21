import pytest
import os
import tarfile
from flask import Flask

from core.schains.runner import get_image_name
from tools.configs.containers import SCHAIN_CONTAINER

from tools.configs import NODE_DATA_PATH
from tests.utils import get_bp_data
from web.routes.logs import web_logs
from tools.docker_utils import DockerUtils
from web.helper import get_api_url


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    app.register_blueprint(web_logs)
    return app.test_client()


def test_get_logs(skale_bp):
    cont_name = 'logs_test'
    dutils = DockerUtils(volume_driver='local')
    schain_image = get_image_name(SCHAIN_CONTAINER)
    dutils.client.containers.run(schain_image, name=cont_name, detach=True)
    data = get_bp_data(
        skale_bp,
        get_api_url('logs', 'dump'),
        {'container_name': cont_name},
        full_data=True
    )
    schain_log_path = os.path.join(NODE_DATA_PATH, 'logs.tar.gz')
    with open(schain_log_path, 'wb') as f:
        f.write(data)
    tar = tarfile.open(schain_log_path, "r:gz")
    assert f'{cont_name}.log' in tar.getnames()
    os.remove(schain_log_path)
    dutils.safe_rm(cont_name, force=True)
