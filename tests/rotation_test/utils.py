import json
from time import sleep

from skale.manager_client import spawn_skale_lib

from core.node import Node
from core.schains.checks import check_endpoint_alive
from core.schains.config import get_skaled_http_address
from core.schains.runner import run_schain_container, check_container_exit
from core.schains.volume import init_data_volume
from tests.dkg_test.main_test import (generate_sgx_wallets, transfer_eth_to_wallets,
                                      link_addresses_to_validator, register_nodes, run_dkg_all)
from tests.utils import generate_random_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.docker_utils import DockerUtils

docker_utils = DockerUtils(volume_driver='local')

TIMEOUT = 240
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


class NodeConfigMock:
    def __init__(self):
        self.id = 0
        self.sgx_key_name = ""


def run_dkg_mock(skale, schain_name, node_id, sgx_key_name, rotation_id):
    path = get_secret_key_share_filepath(schain_name, rotation_id)
    with open(path, 'w') as file:
        file.write(json.dumps(SECRET_KEY_INFO))
    return True


def init_data_volume_mock(schain, dutils):
    return init_data_volume(schain, docker_utils)


def run_schain_container_mock(schain, env):
    return run_schain_container(schain, env, docker_utils)


def set_up_nodes(skale, nodes_number):
    wallets = generate_sgx_wallets(skale, nodes_number)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    nodes_data = register_nodes(skale, wallets)
    return nodes_data


def set_up_rotated_schain(skale):
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

    return nodes, schain_name


def get_spawn_skale_mock(node_id):
    def spawn_skale_lib_mock(skale):
        mocked_skale = spawn_skale_lib(skale)

        def get_node_ids_mock(name):
            return [node_id]

        mocked_skale.schains_internal.get_node_ids_for_schain = get_node_ids_mock
        return mocked_skale
    return spawn_skale_lib_mock


def wait_for_contract_exiting(skale, node_id):
    sum_time = 0
    while skale.nodes.get_node_status(node_id) != 2 and sum_time < TIMEOUT:
        sum_time += 10
        sleep(10)
    assert sum_time < TIMEOUT


def wait_for_schain_alive(schain_name):
    schain_endpoint = get_skaled_http_address(schain_name)
    schain_endpoint = f'http://{schain_endpoint.ip}:{schain_endpoint.port}'
    sum_time = 0
    while not check_endpoint_alive(schain_endpoint) and sum_time < TIMEOUT:
        sum_time += 10
        sleep(10)
    assert sum_time < TIMEOUT


def wait_for_schain_exiting(schain_name):
    sum_time = 0
    while not check_container_exit(schain_name, dutils=docker_utils) and sum_time < TIMEOUT:
        sum_time += 10
        sleep(10)
    assert sum_time < TIMEOUT


def check_schain_alive(schain_name):
    schain_endpoint = get_skaled_http_address(schain_name)
    schain_endpoint = f'http://{schain_endpoint.ip}:{schain_endpoint.port}'
    return check_endpoint_alive(schain_endpoint)
