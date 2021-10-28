from time import sleep

from skale.skale_manager import spawn_skale_manager_lib

from core.node import Node
from core.schains.checks import check_endpoint_alive
from core.schains.config.helper import get_skaled_http_address
from core.schains.runner import run_schain_container, is_exited
from core.schains.volume import init_data_volume

from tests.utils import generate_random_schain_data, init_skale_from_wallet

from tests.dkg_test.main_test import (create_schain,
                                      generate_sgx_wallets,
                                      transfer_eth_to_wallets,
                                      link_addresses_to_validator,
                                      register_nodes, run_dkg_all)


TIMEOUT = 240


class NodeConfigMock:
    def __init__(self):
        self.id = 0
        self.ip = '1.1.1.1'
        self.name = 'node0'
        self.sgx_key_name = ""

    def all(self):
        return {
            'node_id': self.id,
            'node_ip': self.ip,
            'name': self.name,
            'sgx_key_name': self.sgx_key_name
        }


def init_data_volume_mock(schain, dutils=None):
    return init_data_volume(schain, dutils)


def run_schain_container_mock(schain, public_key=None, start_ts=None,
                              dutils=None):
    return run_schain_container(
        schain, public_key=public_key,
        start_ts=start_ts,
        dutils=dutils,
        volume_mode='Z',
        ulimit_check=False,
        enable_ssl=False
    )


def delete_bls_keys_mock(self, bls_key_name):
    return bls_key_name


def set_up_nodes(skale, nodes_number):
    wallets = generate_sgx_wallets(skale, nodes_number)
    transfer_eth_to_wallets(skale, wallets)
    link_addresses_to_validator(skale, wallets)
    skale_instances = [init_skale_from_wallet(wallet) for wallet in wallets]
    nodes_data = register_nodes(skale_instances)
    return nodes_data, skale_instances


def set_up_rotated_schain(skale, schain_name=None):
    nodes_data, skale_instances = set_up_nodes(skale, 2)

    _, lifetime_seconds, new_name = generate_random_schain_data()
    schain_name = new_name
    create_schain(skale, schain_name, lifetime_seconds)
    run_dkg_all(skale, skale_instances, schain_name, nodes_data)

    [new_node_data], [new_skale_instance] = set_up_nodes(skale, 1)
    nodes_data.append(new_node_data)
    skale_instances.append(new_skale_instance)
    nodes = []
    for node, node_skale in zip(nodes_data, skale_instances):
        config = NodeConfigMock()
        config.id = node['node_id']
        config.sgx_key_name = node_skale.wallet.key_name
        nodes.append(Node(node_skale, config))

    return nodes, schain_name


def get_spawn_skale_mock(node_id):
    def spawn_skale_lib_mock(skale):
        mocked_skale = spawn_skale_manager_lib(skale)

        def get_node_ids_mock(name):
            return [node_id]

        mocked_skale.schains_internal.get_node_ids_for_schain = get_node_ids_mock
        return mocked_skale
    return spawn_skale_lib_mock


def wait_for_contract_exiting(skale, node_id):
    sum_time = 0
    while skale.nodes.get_node_status(node_id) != 2 and sum_time < TIMEOUT:
        sum_time += 10
        sleep(2)
    assert sum_time < TIMEOUT


def wait_for_schain_alive(schain_name):
    schain_endpoint = get_skaled_http_address(schain_name)
    schain_endpoint = f'http://{schain_endpoint.ip}:{schain_endpoint.port}'
    sum_time = 0
    while not check_endpoint_alive(schain_endpoint) and sum_time < TIMEOUT:
        sum_time += 10
        sleep(10)
    assert sum_time < TIMEOUT


def wait_for_schain_exiting(schain_name, dutils):
    sum_time = 0
    while not is_exited(schain_name, dutils=dutils) and sum_time < TIMEOUT:
        sum_time += 10
        sleep(10)
    assert sum_time < TIMEOUT


def check_schain_alive(schain_name):
    schain_endpoint = get_skaled_http_address(schain_name)
    schain_endpoint = f'http://{schain_endpoint.ip}:{schain_endpoint.port}'
    return check_endpoint_alive(schain_endpoint)
