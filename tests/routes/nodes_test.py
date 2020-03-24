import pytest
from flask import Flask

from tools.docker_utils import DockerUtils
from core.node import Node
from core.node_config import NodeConfig
from tests.utils import get_bp_data
from web.routes.nodes import construct_nodes_bp

from skale.utils.contracts_provision.utils import generate_random_node_data


@pytest.fixture
def skale_bp(skale):
    app = Flask(__name__)
    node_config = NodeConfig()
    node = Node(skale, node_config)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_nodes_bp(skale, node, dutils))
    return app.test_client()


def test_check_node_name(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': 'test'})
    assert data == True
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': name})
    assert data == False
    node_idx = skale.nodes_data.node_name_to_index(name)
    skale.manager.delete_node_by_root(node_idx, wait_for=True)


def test_check_node_ip(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': '0.0.0.0'})
    assert data == True
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': ip})
    assert data == False
    node_idx = skale.nodes_data.node_name_to_index(name)
    skale.manager.delete_node_by_root(node_idx, wait_for=True)


def test_containers_list(skale_bp, skale):
    dutils = DockerUtils(volume_driver='local')
    data = get_bp_data(skale_bp, '/containers/list')
    assert data == dutils.get_all_skale_containers(format=True)
    data = get_bp_data(skale_bp, '/containers/list', {'all': True})
    assert data == dutils.get_all_skale_containers(all=all, format=True)
