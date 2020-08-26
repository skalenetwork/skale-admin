import json
from time import sleep

from skale.skale_manager import spawn_skale_manager_lib

from core.node import Node
from core.schains.checks import check_endpoint_alive
from core.schains.config.helper import get_skaled_http_address
from core.schains.runner import run_schain_container, check_container_exit
from core.schains.volume import init_data_volume
from sgx import SgxClient
from sgx.sgx_rpc_handler import SgxServerError
from tools.configs import SGX_SERVER_URL, SGX_CERTIFICATES_FOLDER
from tests.dkg_test.main_test import (generate_sgx_wallets, transfer_eth_to_wallets,
                                      link_addresses_to_validator, register_nodes, run_dkg_all)
from tests.utils import generate_random_name
from tools.bls.dkg_utils import get_secret_key_share_filepath
from tools.docker_utils import DockerUtils

docker_utils = DockerUtils(volume_driver='local')

TIMEOUT = 240
INSECURE_PRIVATE_KEY = "f253bad7b1f62b8ff60bbf451cf2e8e9ebb5d6e9bff450c55b8d5504b8c63d3"
SECRET_KEY_INFO = {
    "common_public_key": [
        "15959969554621958245201075983340071881770733084910870228938077786643587385029",
        "7970122607051572307517094692346020360016825923464107614135327251488152616550",
        "3371162264373897025322009434717052197952692496405149486989861571246537813591",
        "13678625751515504401110635369790787716744686498431213713911601759809559919693"
    ],
    "public_key": [
        "15959969554621958245201075983340071881770733084910870228938077786643587385029",
        "7970122607051572307517094692346020360016825923464107614135327251488152616550",
        "3371162264373897025322009434717052197952692496405149486989861571246537813591",
        "13678625751515504401110635369790787716744686498431213713911601759809559919693"
    ],
    "t": 1,
    "n": 1,
    "key_share_name": "BLS_KEY:SCHAIN_ID:1:NODE_ID:0:DKG_ID:0"
}


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


def run_dkg_mock(skale, schain_name, node_id, sgx_key_name, rotation_id):
    path = get_secret_key_share_filepath(schain_name, rotation_id)
    with open(path, 'w') as file:
        file.write(json.dumps(SECRET_KEY_INFO))
    import_bls_key()
    return True


def init_data_volume_mock(schain, dutils):
    return init_data_volume(schain, docker_utils)


def run_schain_container_mock(schain, public_key=None, start_ts=None):
    return run_schain_container(schain, public_key=public_key,
                                start_ts=start_ts, dutils=docker_utils)


def delete_bls_keys_mock(self, bls_key_name):
    return bls_key_name


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
        skale_lib = spawn_skale_manager_lib(skale)
        skale_lib.wallet = node['wallet']
        config = NodeConfigMock()
        config.id = node['node_id']
        config.sgx_key_name = skale_lib.wallet.key_name
        nodes.append(Node(skale_lib, config))

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


def import_bls_key():
    sgx_client = SgxClient(SGX_SERVER_URL, n=1, t=1, path_to_cert=SGX_CERTIFICATES_FOLDER)
    try:
        sgx_client.import_bls_private_key(
            SECRET_KEY_INFO['key_share_name'], INSECURE_PRIVATE_KEY
        )
    except SgxServerError as e:
        if str(e) == 'Key share with this name already exists':
            pass
