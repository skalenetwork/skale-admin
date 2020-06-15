from time import sleep, time
from unittest import mock

import pytest
import json
import os

from skale.manager_client import spawn_skale_lib

from core.node import Node, NodeExitStatuses, SchainExitStatuses
from core.node_config import NodeConfig
from core.schains.checks import check_endpoint_alive, SChainChecks
from core.schains.cleaner import monitor as cleaner_monitor
from core.schains.config import get_skaled_http_address
from core.schains.creator import monitor
from core.schains.runner import run_schain_container, check_container_exit
from core.schains.volume import init_data_volume
from tests.dkg_test.main_test import run_dkg_all, generate_sgx_wallets, transfer_eth_to_wallets, \
    link_addresses_to_validator, register_nodes
from tests.utils import generate_random_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.docker_utils import DockerUtils
from web.models.schain import SChainRecord
from tools.configs import SSL_CERTIFICATES_FILEPATH

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


def set_up_nodes(skale, nodes_number):
    wallets = generate_sgx_wallets(skale, nodes_number)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    nodes_data = register_nodes(skale, wallets)
    return nodes_data


@pytest.fixture
def exiting_node(skale):
    nodes = set_up_nodes(skale, 2)
    config = NodeConfig()
    config.id = nodes[0]['node_id']

    schain_name = generate_random_name()
    skale.manager.create_default_schain(schain_name)

    run_dkg_all(skale, schain_name, nodes)
    nodes.append(set_up_nodes(skale, 1)[0])

    exit_skale_lib = spawn_skale_lib(skale)
    exit_skale_lib.wallet = nodes[0]['wallet']

    key_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_key')
    cert_path = os.path.join(SSL_CERTIFICATES_FILEPATH, 'ssl_cert')
    os.remove(key_path)
    os.remove(cert_path)

    yield Node(exit_skale_lib, config), schain_name

    with open(cert_path, 'w') and open(key_path, 'w'):
        pass
    skale.manager.delete_schain(schain_name, wait_for=True)
    for i in range(1, 3):
        skale.manager.delete_node_by_root(nodes[i]['node_id'], wait_for=True)


def test_node_exit(skale, exiting_node):
    node = exiting_node[0]
    schain_name = exiting_node[1]

    def spawn_skale_lib_mock(skale):
        mocked_skale = spawn_skale_lib(skale)

        def get_node_ids_mock(name):
            return [node.config.id]

        mocked_skale.schains_data.get_node_ids_for_schain = get_node_ids_mock
        return mocked_skale

    SChainRecord.create_table()
    with mock.patch('core.schains.creator.add_firewall_rules'), \
            mock.patch('core.schains.creator.run_dkg', run_dkg_mock),\
            mock.patch('core.schains.creator.init_data_volume', init_data_volume_mock), \
            mock.patch('core.schains.creator.run_schain_container', run_schain_container_mock), \
            mock.patch('core.schains.creator.spawn_skale_lib', spawn_skale_lib_mock), \
            mock.patch('core.schains.checks.apsent_iptables_rules',
                       new=mock.Mock(return_value=[True, True])):
        monitor(skale, node.config)
        node.exit({})
        while skale.nodes_data.get_node_status(node.config.id) != 2:
            sleep(10)
        exit_status = node.get_exit_status()
        assert exit_status['status'] == NodeExitStatuses.WAIT_FOR_ROTATIONS.name
        assert exit_status['data'][0]['status'] == SchainExitStatuses.LEAVING.name

        schain_endpoint = get_skaled_http_address(schain_name)
        schain_endpoint = f'http://{schain_endpoint.ip}:{schain_endpoint.port}'
        while not check_endpoint_alive(schain_endpoint):
            sleep(10)

        monitor(skale, node.config)
        assert check_endpoint_alive(schain_endpoint)

        finish_time = time()
        rotation_mock = {
            'result': True,
            'new_schain': False,
            'exiting_node': True,
            'finish_ts': finish_time,
            'rotation_id': 1
        }
        with mock.patch('core.schains.creator.check_for_rotation',
                        new=mock.Mock(return_value=rotation_mock)):
            monitor(skale, node.config)
            while not check_container_exit(schain_name, dutils=dutils):
                sleep(10)

            cleaner_monitor(node.skale, node.config)
            checks = SChainChecks(schain_name, node.config.id).get_all()
            assert not checks['container']
            assert not checks['volume']
            assert not checks['data_dir']
            assert not checks['config']
