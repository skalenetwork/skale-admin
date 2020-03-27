import pytest
from mock import patch

from flask import Flask

from tools.docker_utils import DockerUtils
from core.node import Node
from core.node_config import NodeConfig
from tests.utils import get_bp_data, post_bp_data
from web.routes.nodes import construct_nodes_bp

from skale.utils.contracts_provision.utils import generate_random_node_data


@pytest.fixture
def node_config(skale):
    return NodeConfig()


@pytest.fixture
def node(skale, node_config):
    node = Node(skale, node_config)
    return node


@pytest.fixture
def skale_bp(skale, node):
    app = Flask(__name__)
    dutils = DockerUtils(volume_driver='local')
    app.register_blueprint(construct_nodes_bp(skale, node, dutils))
    return app.test_client()


def test_check_node_name(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': 'test'})
    assert data is True
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-name', {'nodeName': name})
    assert data is False
    node_idx = skale.nodes_data.node_name_to_index(name)
    skale.manager.delete_node_by_root(node_idx, wait_for=True)


def test_check_node_ip(skale_bp, skale):
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': '0.0.0.0'})
    assert data is True
    ip, public_ip, port, name = generate_random_node_data()
    skale.manager.create_node(ip, port, name, wait_for=True)
    data = get_bp_data(skale_bp, '/check-node-ip', {'nodeIp': ip})
    assert data is False
    node_idx = skale.nodes_data.node_name_to_index(name)
    skale.manager.delete_node_by_root(node_idx, wait_for=True)


def test_containers_list(skale_bp, skale):
    dutils = DockerUtils(volume_driver='local')
    data = get_bp_data(skale_bp, '/containers/list')
    assert data == dutils.get_all_skale_containers(format=True)
    data = get_bp_data(skale_bp, '/containers/list', {'all': True})
    assert data == dutils.get_all_skale_containers(all=all, format=True)


def test_node_info(skale_bp, node):
    data = get_bp_data(skale_bp, '/node-info')
    assert data == node.info


def register_mock(self, ip, public_ip, port, name):
    return {'status': 1, 'data': 1}


@patch.object(Node, 'register', register_mock)
def test_node_create(skale_bp, node_config):
    ip, public_ip, port, name = generate_random_node_data()
    json_data = {
        'name': name,
        'ip': ip,
        'publicIP': public_ip,
        'port': port
    }
    data = post_bp_data(skale_bp, '/create-node', json_data)
    assert data == 1
