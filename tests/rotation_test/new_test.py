from time import sleep
from unittest import mock

import pytest
import json
import os

from skale.manager_client import spawn_skale_lib

from core.node import Node
from core.schains.checks import SChainChecks
from core.schains.creator import monitor
from core.schains.runner import run_schain_container
from core.schains.volume import init_data_volume
from tests.dkg_test.main_test import (
    run_dkg_all, generate_sgx_wallets, transfer_eth_to_wallets,
    link_addresses_to_validator, register_nodes
)
from tests.utils import generate_random_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord
from tools.configs import SSL_CERTIFICATES_FILEPATH

dutils = DockerUtils(volume_driver='local')


class NodeConfigMock():
    def __init__(self):
        self.id = 0
        self.sgx_key_name = ""


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


def set_up_nodes(skale, nodes_number):
    wallets = generate_sgx_wallets(skale, nodes_number)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    nodes_data = register_nodes(skale, wallets)
    return nodes_data


@pytest.fixture
def rotated_nodes(skale):
    SChainRecord.create_table()
    nodes_data = set_up_nodes(skale, 2)

    schain_name = generate_random_name()
    skale.manager.create_default_schain(schain_name)

    run_dkg_all(skale, schain_name, nodes_data)
    nodes_data.append(set_up_nodes(skale, 1)[0])
    nodes = []
    for node in nodes_data:
        skale_lib = spawn_skale_lib(skale)
        skale_lib.wallet = node['wallet']
        config = NodeConfigMock()
        config.id = node['node_id']
        nodes.append(Node(skale_lib, config))

    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')

    yield nodes, schain_name

    with open(cert_path, 'w') and open(key_path, 'w'):
        pass

    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.delete_node_by_root(nodes_data[i]['node_id'], wait_for=True)


def test_new_node(skale, rotated_nodes):
    nodes, schain_name = rotated_nodes
    exited_node, new_node = nodes[0], nodes[2]
    exited_node.exit({})

    while skale.nodes_data.get_node_status(nodes[0].config.id) != 2:
        sleep(10)

    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_schain_container'), \
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(new_node.skale, new_node.config)
        checks = SChainChecks(schain_name, new_node.config.id).get_all()
        assert checks['container']
        assert checks['volume']
        assert checks['data_dir']
        assert checks['config']
