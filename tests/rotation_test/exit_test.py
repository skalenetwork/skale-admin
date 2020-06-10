from unittest import mock

import pytest
import json

from core.node import Node
from core.node_config import NodeConfig
from core.schains.creator import monitor
from core.schains.runner import run_schain_container
from core.schains.volume import init_data_volume
from tests.utils import generate_random_node_data
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord

dutils = DockerUtils(volume_driver='local')

SECRET_KEY_INFO = {
    "common_public_key": [
        1
    ],
    "public_key": [
        "1",
        "1",
        "1",
        "1"
    ],
    "t": 3,
    "n": 4,
    "key_share_name": "BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0"
}


def run_dkg_mock(skale, schain_name, node_id, sgx_key_name, rotation_id):
    path = get_secret_key_share_filepath(schain_name, rotation_id)
    with open(path, 'w') as file:
        file.write(json.dumps(SECRET_KEY_INFO))
    return True


def init_data_volume_mock(schain):
    return init_data_volume(schain, dutils)


def run_schain_container_mock(schain, env):
    return run_schain_container(schain, env, dutils)


@pytest.fixture
def exiting_node(skale):
    name = 'exit_test'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)
    config = NodeConfig()
    config.id = skale.nodes_data.node_name_to_index(name)

    name = f'rotation_test_0'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)

    schain_name = 'exit_schain'
    skale.manager.create_default_schain(schain_name)

    name = f'rotation_test_1'
    ip, public_ip, port, _ = generate_random_node_data()
    skale.manager.create_node(ip, port, name, public_ip, wait_for=True)

    yield Node(skale, config)
    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(2):
        name = f'rotation_test_{i}'
        id = skale.nodes_data.node_name_to_index(name)
        skale.manager.delete_node_by_root(id, wait_for=True)


def test_node_exit(skale, exiting_node):
    SChainRecord.create_table()
    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock),\
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(skale, exiting_node.config)
