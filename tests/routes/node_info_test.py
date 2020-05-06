import pytest
import pkg_resources
from flask import Flask

from tools.docker_utils import DockerUtils
from tools.configs.web3 import ENDPOINT
from tests.utils import get_bp_data
from web.routes.node_info import construct_node_info_bp
from tools.configs.flask import SKALE_LIB_NAME


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_node_info_bp(skale, dutils))
    return app.test_client()


def test_rpc_healthcheck(skale_bp):
    data = get_bp_data(skale_bp, '/get-rpc-credentials')
    expected = {
        'status': 'ok',
        'payload': {
            'endpoint': ENDPOINT
        }
    }
    assert data == expected


def test_containers_healthcheck(skale_bp):
    data = get_bp_data(skale_bp, '/healthchecks/containers')
    dutils = DockerUtils(volume_driver='local')
    expected = {
        'status': 'ok',
        'payload': dutils.get_all_skale_containers(all=all, format=True)
    }
    assert data == expected


def test_about(skale_bp, skale):
    expected = {
        'status': 'ok',
        'payload': {
            'libraries': {
                'javascript': 'N/A',  # get_js_package_version(),
                'skale.py': pkg_resources.get_distribution(SKALE_LIB_NAME).version
            },
            'contracts': {
                'token': skale.token.address,
                'manager': skale.manager.address,
            },
            'network': {
                'endpoint': ENDPOINT
            }
        }
    }
    data = get_bp_data(skale_bp, '/about-node')
    assert data == expected
